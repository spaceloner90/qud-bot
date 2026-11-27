// Qud bot bridge: lets a Python "brain" read the game and press keys, the way a player would.
//
// Output: whenever the game is about to wait for a key, the mod can snapshot what is on screen (the
// classic 80x25 text buffer, with colours) plus a few structured facts (player, zone, messages).
// Input: the brain answers with keys or named commands, which go into the game's own key queue, so
// the game handles them exactly like key presses. Nothing else in the game is changed.
//
// Controls, in game (classic UI, "Enable modern UI" off, so every screen reads keys the same way):
//   F1  run: keep asking the brain at every key wait until it says STOP, or until any key is pressed
//   F7  step: ask the brain once and play what it answers
//   F8  report: write the snapshot and log it, without playing anything
//   F9  narrator voice on/off (live/voice_on, read by tools/narrator.ps1); F10 bot panel on/off
//
// Every exchange is appended to live/log.jsonl; the latest snapshot is in live/state.json and
// live/screen.txt. The brain runs as a new process per call, so brain edits apply on the next call.
//
// Written for C# 5 (checked with the compiler that ships with Windows), though the game compiles it
// with its own Roslyn.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using ConsoleLib.Console;
using HarmonyLib;
using XRL;
using XRL.Core;
using XRL.World;
using KeyCode = UnityEngine.KeyCode;

namespace QudBot
{
    public static class Bot
    {
        // The repo folder: written into the installed copy by tools/deploy_mod.ps1 (not hard-coded in the repo).
        public const string Root = @"__QUDBOT_ROOT__";
        public const string LiveDir = Root + @"\live";
        public const string BrainScript = Root + @"\brain\step.py";
        public const string Python = "python";
        // Decisions live in brain/bridge.json, reread whenever it changes (no game restart):
        //   ask_during_autoact  ask the brain on the map while the game's own automatic action runs
        //   max_calls_per_run   a run stops after this many brain calls
        //   brain_timeout_ms    a brain call that takes longer counts as an error
        public const string ConfigPath = Root + @"\brain\bridge.json";

        public const KeyCode RunKey = KeyCode.F1;
        // Control keys are swallowed and this unbound key is pushed in their place, so the game never
        // sees them (F1 is the game's Help key) but a waiting GetNextKey still wakes up.
        public const KeyCode WakeKey = KeyCode.F6;
        public const KeyCode StepKey = KeyCode.F7;
        public const KeyCode ReportKey = KeyCode.F8;
        public const UnityEngine.InputSystem.Key RunInputKey = UnityEngine.InputSystem.Key.F1;
        public const UnityEngine.InputSystem.Key StepInputKey = UnityEngine.InputSystem.Key.F7;
        public const UnityEngine.InputSystem.Key ReportInputKey = UnityEngine.InputSystem.Key.F8;

        // Set from the Unity thread when a control key is pressed; read on the game thread.
        public static volatile bool Running;
        public static volatile bool StepRequested;
        public static volatile bool ReportRequested;
        public static volatile bool StopRequested;

        // True while the mod itself pushes keys, so they aren't mistaken for the player's.
        [ThreadStatic] public static bool Injecting;

        public static int Sequence;
        public static int CallsThisRun;
        public static string LastScreenHash;
        public static int SameScreenCalls;

        private static readonly object LogGate = new object();

        // Called on the game thread right before the game waits for a key.
        // "map" when the map loop is idle (IdleWait), "key" when a menu, popup or prompt waits for a key,
        // "picker" when a cell picker (Move to, targeting) waits.
        public static string WaitKind = "key";

        // Set by control keys on Unity's thread; the message is shown from the game thread.
        public static volatile string PendingSay;
        public static volatile string LastGotoFailed;  // the last GOTO with no path, for the next snapshot
        public static volatile int AimX = -1, AimY = -1;  // AIM x y: the next cell picker returns this cell

        // One line per player turn during runs (live/turns.jsonl): where the player is and which of the
        // game's automatic actions is running. The game doesn't idle between autoexplore steps, so the
        // key-wait hooks can't record its route; the begin-turn callback can.
        private static Action<XRLCore> turnCallback;

        private static void EnsureTurnTrace()
        {
            if (turnCallback == null) turnCallback = new Action<XRLCore>(OnBeginPlayerTurn);
            // The list is private; the game may clear it when a game loads, so check it each time.
            List<Action<XRLCore>> registered = AccessTools.Field(typeof(XRLCore), "OnBeginPlayerTurnCallbacks").GetValue(null) as List<Action<XRLCore>>;
            if (registered == null || !registered.Contains(turnCallback)) XRLCore.RegisterOnBeginPlayerTurnCallback(turnCallback);
        }

        private static void OnBeginPlayerTurn(XRLCore core)
        {
            if (!Running) return;
            try
            {
                Cell cell = The.Player.CurrentCell;
                string autoact = XRL.World.Capabilities.AutoAct.IsActive(false) ? (XRL.World.Capabilities.AutoAct.Setting ?? "") : null;
                string line = "{\"turn\":" + XRLCore.CurrentTurn + ",\"zone\":" + Json.Str(cell.ParentZone.ZoneID)
                    + ",\"x\":" + cell.X + ",\"y\":" + cell.Y + ",\"hp\":" + The.Player.hitpoints
                    + ",\"autoact\":" + Json.Str(autoact) + "}\n";
                File.AppendAllText(LiveDir + @"\turns.jsonl", line, new UTF8Encoding(false));
            }
            catch { }
            try { CheckAutoactInterrupt(); } catch { }
        }

        // Breaking off autoexplore for creatures the brain names (v0.26, 2026-11-26). The game doesn't
        // ask the brain between autoexplore steps, so the brain can't stop it for prey it passes; instead
        // it lists the kinds in live/interrupt.txt (first line: radius; then one lower-case kind per line,
        // matched as a substring of the display name). Each turn of autoexplore, a visible creature of a
        // listed kind within the radius interrupts it, once per creature per zone. Which kinds is the
        // brain's decision; this is only the mechanism.
        private static DateTime interruptMtime = DateTime.MinValue;
        private static string[] interruptKinds = new string[0];
        private static int interruptRadius = 12;
        private static string interruptZone;
        private static HashSet<string> interruptedIds = new HashSet<string>();

        private static void CheckAutoactInterrupt()
        {
            if (!XRL.World.Capabilities.AutoAct.IsActive(false)) return;
            string path = LiveDir + @"\interrupt.txt";
            if (!File.Exists(path)) return;
            DateTime m = File.GetLastWriteTimeUtc(path);
            if (m != interruptMtime)
            {
                interruptMtime = m;
                List<string> kinds = new List<string>();
                string[] lines = File.ReadAllLines(path, new UTF8Encoding(false));
                int r;
                if (lines.Length > 0 && int.TryParse(lines[0].Trim(), out r)) interruptRadius = r;
                for (int i = 1; i < lines.Length; i++)
                {
                    string k = lines[i].Trim().ToLowerInvariant();
                    if (k.Length > 0) kinds.Add(k);
                }
                interruptKinds = kinds.ToArray();
            }
            if (interruptKinds.Length == 0) return;
            GameObject player = The.Player;
            Cell here = player.CurrentCell;
            Zone zone = here.ParentZone;
            if (zone.ZoneID != interruptZone) { interruptZone = zone.ZoneID; interruptedIds.Clear(); }
            for (int y = Math.Max(0, here.Y - interruptRadius); y <= Math.Min(zone.Height - 1, here.Y + interruptRadius); y++)
            {
                for (int x = Math.Max(0, here.X - interruptRadius); x <= Math.Min(zone.Width - 1, here.X + interruptRadius); x++)
                {
                    if (!zone.GetVisibility(x, y)) continue;
                    foreach (GameObject o in zone.GetCell(x, y).Objects)
                    {
                        if (o == null || o == player || !o.IsCreature || !o.IsVisible()) continue;
                        string name = (o.DisplayNameOnlyStripped ?? "").ToLowerInvariant();
                        bool listed = false;
                        foreach (string k in interruptKinds) if (name.Contains(k)) { listed = true; break; }
                        if (!listed) continue;
                        string id = o.ID;
                        if (id == null || interruptedIds.Contains(id)) continue;
                        interruptedIds.Add(id);
                        XRL.World.Capabilities.AutoAct.Interrupt(o, true, false);
                        AppendLog("{\"kind\":\"autoact_interrupt\",\"turn\":" + XRLCore.CurrentTurn + ",\"name\":" + Json.Str(name)
                            + ",\"id\":" + Json.Str(id) + ",\"x\":" + x + ",\"y\":" + y + "}");
                        return;
                    }
                }
            }
        }

        public static void OnKeyWait()
        {
            try { EnsureTurnTrace(); } catch { }
            string say = PendingSay;
            if (say != null)
            {
                PendingSay = null;
                Say(say);
            }
            if (StopRequested)
            {
                StopRequested = false;
                if (Running) Stop("stopped by a key press");
            }
            if (Keyboard.HasKey() || Keyboard.HasMouseEvent(false)) return;

            if (ReportRequested)
            {
                ReportRequested = false;
                string state = Snapshot.Build("report");
                WriteLive(state);
                AppendLog("{\"seq\":" + Sequence + ",\"kind\":\"report\",\"state\":" + state + "}");
                Say("Bot: report written (seq " + Sequence + ").");
            }

            if (!Running && !StepRequested) return;
            // Let the game's own automatic actions (autoexplore, resting, auto-walk) run to their end;
            // the bot gets asked again once they stop.
            // Only on the map: a popup can open while an automatic action is still marked active
            // (autoexplore examining a shrine), and that popup needs an answer.
            Config.Refresh();
            try { if (WaitKind == "map" && !Config.AskDuringAutoAct && XRL.World.Capabilities.AutoAct.IsActive(false)) return; } catch { }
            bool step = StepRequested;
            StepRequested = false;

            if (Running && ++CallsThisRun > Config.MaxCallsPerRun)
            {
                Stop("hit the limit of " + Config.MaxCallsPerRun + " brain calls per run");
                return;
            }
            // A brain that answers WAIT is asked again (it can block for a while itself), until it
            // gives keys or stops, or the player presses a key. This is how the LLM drives a run live.
            string mode = Running ? "run" : "step";
            while (AskBrain(mode) && Running)
            {
                if (StopRequested)
                {
                    StopRequested = false;
                    Stop("stopped by a key press");
                    return;
                }
                Thread.Sleep(50);
            }
        }

        // Returns true if the brain answered WAIT: nothing to play yet, ask again.
        private static bool AskBrain(string mode)
        {
            string state = Snapshot.Build(mode);
            WriteLive(state);
            Stopwatch timer = Stopwatch.StartNew();
            string answer;
            string error = null;
            try
            {
                answer = RunBrain(state);
            }
            catch (Exception ex)
            {
                answer = "";
                error = ex.Message;
            }
            long ms = timer.ElapsedMilliseconds;

            List<string> pushed = new List<string>();
            bool wait = false;
            bool pass = false;
            string stopReason = error != null ? "brain error: " + error : null;
            foreach (string raw in answer.Replace("\r\n", "\n").Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length == 0) continue;
                int space = line.IndexOf(' ');
                string verb = space < 0 ? line : line.Substring(0, space);
                string arg = space < 0 ? "" : line.Substring(space + 1).Trim();
                if (verb == "KEY")
                {
                    string problem = KeyInput.PushKey(arg);
                    if (problem != null) { stopReason = problem; break; }
                    pushed.Add(arg);
                }
                else if (verb == "CMD")
                {
                    KeyInput.PushCommand(arg);
                    pushed.Add("CMD " + arg);
                }
                else if (verb == "SAY")
                {
                    Say("Bot: " + arg);
                }
                else if (verb == "STOP")
                {
                    stopReason = arg.Length > 0 ? arg : "the brain stopped";
                }
                else if (verb == "WAIT")
                {
                    wait = true;
                }
                else if (verb == "PASS")
                {
                    pass = true;
                }
                else if (verb == "AIM")
                {
                    // The next target picker (Teleport, rays, throwing) returns cell x,y directly instead of
                    // being driven by cursor keys (2026-11-24: batched cursor keys were dropped and a teleport
                    // went the wrong way). Plays nothing now; also counts as an action so the run goes on.
                    string[] xy = arg.Split(' ');
                    int ax, ay;
                    if (xy.Length >= 2 && int.TryParse(xy[0], out ax) && int.TryParse(xy[1], out ay)) { AimX = ax; AimY = ay; pass = true; }
                }
                else if (verb == "GOTO")
                {
                    // One step towards cell x,y along the game's own pathfinding (as Move to uses).
                    // No path is information for the brain, not a reason to end the run (2026-11-24: a WALK
                    // to an unexplored cell stopped everything). It's reported in the next snapshot.
                    string problem = GotoStep(arg, pushed);
                    if (problem != null) { LastGotoFailed = problem; pass = true; }
                }
            }
            // A WAIT with nothing else isn't logged: the snapshot is still in live/state.json.
            if (wait && stopReason == null && pushed.Count == 0) return true;
            // PASS: nothing to play now, but the run goes on (the game keeps waiting or acting by itself).
            if (pass && stopReason == null && pushed.Count == 0) return false;
            if (stopReason == null && pushed.Count == 0) stopReason = "the brain gave no keys";

            AppendLog("{\"seq\":" + Sequence + ",\"kind\":\"call\",\"mode\":" + Json.Str(mode) + ",\"ms\":" + ms
                + ",\"answer\":" + Json.Str(answer) + ",\"error\":" + Json.Str(error)
                + ",\"stop\":" + Json.Str(stopReason) + ",\"state\":" + state + "}");

            if (stopReason != null && Running) Stop(stopReason);
            else if (stopReason != null) Say("Bot: " + stopReason);
            return false;
        }

        // "x y": pushes the move command for the first step of the game's path from the player to
        // that cell in the current zone. Returns a problem, or null.
        private static string GotoStep(string arg, List<string> pushed)
        {
            string[] parts = arg.Split(new char[] { ' ', ',' }, StringSplitOptions.RemoveEmptyEntries);
            int x, y;
            if (parts.Length < 2 || !int.TryParse(parts[0], out x) || !int.TryParse(parts[1], out y))
                return "GOTO needs x y, got '" + arg + "'";
            Zone zone = The.Player.CurrentZone;
            if (x < 0 || y < 0 || x >= zone.Width || y >= zone.Height) return "GOTO " + x + "," + y + " is outside the zone";
            Cell here = The.Player.CurrentCell;
            if (here.X == x && here.Y == y) return "GOTO " + x + "," + y + ": already there";
            string step;
            if (!XRL.World.Capabilities.AutoAct.TryFindPathStep(zone.GetCell(x, y), out step) || string.IsNullOrEmpty(step) || step == ".")
                return "GOTO " + x + "," + y + ": no path";
            step = step.ToUpperInvariant();
            KeyInput.PushCommand("CmdMove" + step);
            pushed.Add("CMD CmdMove" + step);
            return null;
        }

        private static string RunBrain(string state)
        {
            ProcessStartInfo info = new ProcessStartInfo(Python, "\"" + BrainScript + "\"");
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardInput = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            info.WorkingDirectory = Root;
            info.StandardOutputEncoding = Encoding.UTF8;
            info.StandardErrorEncoding = Encoding.UTF8;
            using (Process process = Process.Start(info))
            {
                string output = null, errors = null;
                Thread outReader = new Thread(delegate() { output = process.StandardOutput.ReadToEnd(); });
                Thread errReader = new Thread(delegate() { errors = process.StandardError.ReadToEnd(); });
                outReader.IsBackground = true; errReader.IsBackground = true;
                outReader.Start(); errReader.Start();
                using (StreamWriter stdin = new StreamWriter(process.StandardInput.BaseStream, new UTF8Encoding(false)))
                {
                    stdin.Write(state);
                }
                if (!process.WaitForExit(Config.BrainTimeoutMs))
                {
                    try { process.Kill(); } catch { }
                    throw new Exception("the brain took longer than " + Config.BrainTimeoutMs / 1000 + " s");
                }
                outReader.Join(); errReader.Join();
                if (process.ExitCode != 0) throw new Exception("exit " + process.ExitCode + ": " + errors);
                return output ?? "";
            }
        }

        public static void Stop(string reason)
        {
            Running = false;
            CallsThisRun = 0;
            Say("Bot stopped: " + reason);
            AppendLog("{\"seq\":" + Sequence + ",\"kind\":\"stop\",\"reason\":" + Json.Str(reason) + "}");
        }

        // The mod's own notes (run started/stopped, step, report) go to the bot panel's log
        // (live/narration.log, "<turn>\t<text>"), not the game's message log (the user, 2026-11-24).
        public static void Say(string text)
        {
            try
            {
                Directory.CreateDirectory(LiveDir);
                long turn = 0;
                try { turn = XRLCore.CurrentTurn; } catch { }
                File.AppendAllText(LiveDir + @"\narration.log", turn + "\t" + text.Replace("\n", " ") + "\n", new UTF8Encoding(false));
            }
            catch { }
        }

        private static void WriteLive(string state)
        {
            try
            {
                Directory.CreateDirectory(LiveDir);
                File.WriteAllText(Path.Combine(LiveDir, "state.json"), state, new UTF8Encoding(false));
                File.WriteAllText(Path.Combine(LiveDir, "screen.txt"), Snapshot.LastScreenText, new UTF8Encoding(false));
            }
            catch (Exception ex) { UnityEngine.Debug.LogError("QudBot: " + ex); }
        }

        public static void AppendLog(string line)
        {
            lock (LogGate)
            {
                try
                {
                    Directory.CreateDirectory(LiveDir);
                    File.AppendAllText(Path.Combine(LiveDir, "log.jsonl"), line + "\n", new UTF8Encoding(false));
                }
                catch (Exception ex) { UnityEngine.Debug.LogError("QudBot: " + ex); }
            }
        }
    }

    // Reads brain/bridge.json when it changes. Unknown or missing keys keep their defaults.
    public static class Config
    {
        public static bool AskDuringAutoAct = false;
        // Start a run on its own once per game, as soon as the player stands in a zone (the user,
        // 2026-11-24: the bot takes over a new character with an intro as soon as we're in).
        public static bool AutoStart = false;
        public static int MaxCallsPerRun = 3000;
        public static int BrainTimeoutMs = 20000;
        private static DateTime loadedStamp = DateTime.MinValue;

        public static void Refresh()
        {
            try
            {
                if (!File.Exists(Bot.ConfigPath)) return;
                DateTime stamp = File.GetLastWriteTimeUtc(Bot.ConfigPath);
                if (stamp == loadedStamp) return;
                loadedStamp = stamp;
                string text = File.ReadAllText(Bot.ConfigPath);
                AskDuringAutoAct = ReadBool(text, "ask_during_autoact", AskDuringAutoAct);
                AutoStart = ReadBool(text, "auto_start", AutoStart);
                MaxCallsPerRun = ReadInt(text, "max_calls_per_run", MaxCallsPerRun);
                BrainTimeoutMs = ReadInt(text, "brain_timeout_ms", BrainTimeoutMs);
                Bot.AppendLog("{\"kind\":\"config\",\"ask_during_autoact\":" + (AskDuringAutoAct ? "true" : "false")
                    + ",\"max_calls_per_run\":" + MaxCallsPerRun + ",\"brain_timeout_ms\":" + BrainTimeoutMs + "}");
            }
            catch (Exception ex) { UnityEngine.Debug.LogError("QudBot config: " + ex); }
        }

        private static bool ReadBool(string text, string key, bool fallback)
        {
            System.Text.RegularExpressions.Match m = System.Text.RegularExpressions.Regex.Match(text, "\"" + key + "\"\\s*:\\s*(true|false)");
            return m.Success ? m.Groups[1].Value == "true" : fallback;
        }

        private static int ReadInt(string text, string key, int fallback)
        {
            System.Text.RegularExpressions.Match m = System.Text.RegularExpressions.Regex.Match(text, "\"" + key + "\"\\s*:\\s*(-?\\d+)");
            return m.Success ? int.Parse(m.Groups[1].Value) : fallback;
        }
    }

    // An on-screen panel for the bot: a window over the game showing the status the brain writes to
    // live/panel.txt (plan, stage, HP, current action) and, under it, a scrolling log of live/narration.log
    // (everything the bot said and did, newest at the bottom). The mod only draws them; Python decides the
    // content, so it changes without restarts. F10 shows or hides it.
    // Unity's immediate-mode GUI (OnGUI) on a GameObject the mod creates once, on Unity's thread.
    public class BotPanel : UnityEngine.MonoBehaviour
    {
        public static BotPanel Instance;
        public static bool Visible = true;
        private string text = "";
        private DateTime stamp = DateTime.MinValue;
        private float nextRead;
        private UnityEngine.GUIStyle style;

        public static void Ensure()
        {
            if (Instance != null) return;
            UnityEngine.GameObject go = new UnityEngine.GameObject("QudBotPanel");
            UnityEngine.Object.DontDestroyOnLoad(go);
            Instance = go.AddComponent<BotPanel>();
        }

        // The log under the header: the tail of live/narration.log ("<turn>\t<text>" lines, oldest first).
        private const int LogTailBytes = 96 * 1024, LogMaxLines = 600;
        private string log = "";
        private DateTime logStamp = DateTime.MinValue;
        private long logLength = -1;
        private UnityEngine.Vector2 scroll;
        private bool stickToBottom = true;
        private float logHeight;
        private string logHeightFor;
        private float logHeightWidth;
        private int logHeightFont;

        private void Update()
        {
            try { FollowResize(); } catch { resizing = false; }
            if (UnityEngine.Time.unscaledTime < nextRead) return;
            nextRead = UnityEngine.Time.unscaledTime + 0.5f;
            try
            {
                string path = Bot.LiveDir + @"\panel.txt";
                if (!File.Exists(path)) text = "";
                else
                {
                    DateTime t = File.GetLastWriteTimeUtc(path);
                    if (t != stamp) { stamp = t; text = File.ReadAllText(path).TrimEnd(); }
                }
            }
            catch { }
            try { ReadLog(); } catch { }
        }

        private void ReadLog()
        {
            string path = Bot.LiveDir + @"\narration.log";
            if (!File.Exists(path)) { log = ""; return; }
            FileInfo info = new FileInfo(path);
            if (info.LastWriteTimeUtc == logStamp && info.Length == logLength) return;
            logStamp = info.LastWriteTimeUtc;
            logLength = info.Length;
            string tail;
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            {
                long start = Math.Max(0, fs.Length - LogTailBytes);
                fs.Seek(start, SeekOrigin.Begin);
                byte[] buf = new byte[fs.Length - start];
                int got = 0;
                while (got < buf.Length) { int n = fs.Read(buf, got, buf.Length - got); if (n <= 0) break; got += n; }
                tail = Encoding.UTF8.GetString(buf, 0, got);
                if (start > 0) { int nl = tail.IndexOf('\n'); tail = nl >= 0 ? tail.Substring(nl + 1) : ""; }
            }
            string[] lines = tail.Replace("\r", "").TrimEnd('\n').Split('\n');
            int from = Math.Max(0, lines.Length - LogMaxLines);
            StringBuilder sb = new StringBuilder();
            for (int i = from; i < lines.Length; i++)
            {
                if (sb.Length > 0) sb.Append('\n');
                sb.Append(lines[i].Replace("\t", "  "));
            }
            log = sb.ToString();
        }

        // The panel is a window: drag it by any point inside, resize it from the grip in the bottom-right
        // corner. Its place and size are kept in live/panel_layout.json (screen pixels, top-left origin).
        private const int WindowId = 0x51B07;
        private const float Grip = 24f, MinWidth = 220f, MinHeight = 90f;
        private static UnityEngine.Rect rect;
        private static bool rectLoaded;
        private static UnityEngine.Rect savedRect;
        private static bool resizing;
        private static UnityEngine.Vector2 resizeStart, resizeStartSize;
        private UnityEngine.GUIStyle windowStyle;
        private UnityEngine.Texture2D gripTexture;

        private static string LayoutPath { get { return Bot.LiveDir + @"\panel_layout.json"; } }

        private static void LoadLayout()
        {
            rectLoaded = true;
            rect = new UnityEngine.Rect(12, 12, UnityEngine.Screen.width * 0.32f, UnityEngine.Screen.height * 0.3f);
            try
            {
                if (File.Exists(LayoutPath))
                {
                    string s = File.ReadAllText(LayoutPath);
                    float[] v = new float[4];
                    string[] names = { "x", "y", "w", "h" };
                    for (int i = 0; i < 4; i++)
                    {
                        Match m = Regex.Match(s, "\"" + names[i] + "\"\\s*:\\s*(-?[0-9.]+)");
                        if (!m.Success) throw new FormatException(names[i]);
                        v[i] = float.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture);
                    }
                    rect = new UnityEngine.Rect(v[0], v[1], v[2], v[3]);
                }
            }
            catch { }
            savedRect = rect;
        }

        private static void SaveLayout()
        {
            savedRect = rect;
            try
            {
                Directory.CreateDirectory(Bot.LiveDir);
                File.WriteAllText(LayoutPath, string.Format(CultureInfo.InvariantCulture,
                    "{{\"x\": {0:0}, \"y\": {1:0}, \"w\": {2:0}, \"h\": {3:0}}}\n", rect.x, rect.y, rect.width, rect.height));
            }
            catch { }
        }

        // Keeps the window on screen and at least its minimum size (the game window can be resized).
        private static void Clamp()
        {
            float sw = UnityEngine.Screen.width, sh = UnityEngine.Screen.height;
            rect.width = Math.Max(MinWidth, Math.Min(rect.width, sw));
            rect.height = Math.Max(MinHeight, Math.Min(rect.height, sh));
            rect.x = Math.Max(0, Math.Min(rect.x, sw - rect.width));
            rect.y = Math.Max(0, Math.Min(rect.y, sh - rect.height));
        }

        // The mouse in GUI coordinates (top-left origin), from the Input System (bottom-left origin).
        private static bool MouseOverPanel(UnityEngine.InputSystem.Mouse mouse)
        {
            if (mouse == null) return false;
            UnityEngine.Vector2 p = mouse.position.ReadValue();
            return rect.Contains(new UnityEngine.Vector2(p.x, UnityEngine.Screen.height - p.y));
        }

        // Whether the game should skip its input handling this frame: a click on the panel (pressed,
        // held or released), or the wheel over it, would otherwise also reach the map below, where a
        // click walks the player there. Hovering alone doesn't block, so the keyboard keeps working
        // with the mouse resting on the panel.
        private static bool pressStartedOnPanel;
        public static bool ShouldBlockInput()
        {
            if (!Visible || Instance == null || string.IsNullOrEmpty(Instance.text)) { pressStartedOnPanel = false; return false; }
            UnityEngine.InputSystem.Mouse mouse = UnityEngine.InputSystem.Mouse.current;
            if (mouse == null) return false;
            bool anyPressed = mouse.leftButton.wasPressedThisFrame || mouse.rightButton.wasPressedThisFrame || mouse.middleButton.wasPressedThisFrame;
            bool anyHeld = mouse.leftButton.isPressed || mouse.rightButton.isPressed || mouse.middleButton.isPressed;
            bool anyReleased = mouse.leftButton.wasReleasedThisFrame || mouse.rightButton.wasReleasedThisFrame || mouse.middleButton.wasReleasedThisFrame;
            bool over = MouseOverPanel(mouse);
            if (anyPressed) pressStartedOnPanel = over;
            bool block = pressStartedOnPanel && (anyHeld || anyReleased || anyPressed);
            if (!anyHeld && !anyPressed) pressStartedOnPanel = false;
            if (over && mouse.scroll.ReadValue().y != 0) block = true;
            return block || resizing;
        }

        private void OnGUI()
        {
            if (!Visible || string.IsNullOrEmpty(text)) return;
            if (style == null)
            {
                style = new UnityEngine.GUIStyle(UnityEngine.GUI.skin.label);
                style.wordWrap = true;
                style.richText = false;
                style.clipping = UnityEngine.TextClipping.Clip;
                style.normal.textColor = new UnityEngine.Color(0.82f, 0.95f, 0.88f);
                UnityEngine.Texture2D bg = new UnityEngine.Texture2D(1, 1);
                bg.SetPixel(0, 0, new UnityEngine.Color(0f, 0f, 0f, 0.72f));
                bg.Apply();
                windowStyle = new UnityEngine.GUIStyle();
                windowStyle.normal.background = bg;
                windowStyle.onNormal.background = bg;
                gripTexture = new UnityEngine.Texture2D(1, 1);
                gripTexture.SetPixel(0, 0, new UnityEngine.Color(0.82f, 0.95f, 0.88f, 0.5f));
                gripTexture.Apply();
            }
            if (!rectLoaded) LoadLayout();
            style.fontSize = Math.Max(13, UnityEngine.Screen.height / 75);

            UnityEngine.Event e = UnityEngine.Event.current;
            rect = UnityEngine.GUI.Window(WindowId, rect, DrawWindow, UnityEngine.GUIContent.none, windowStyle);
            Clamp();
            if (!resizing && rect != savedRect && e.type == UnityEngine.EventType.Repaint
                && !(UnityEngine.InputSystem.Mouse.current != null && UnityEngine.InputSystem.Mouse.current.leftButton.isPressed))
                SaveLayout();
        }

        private void DrawWindow(int id)
        {
            // Header (status) on top, then the log in a scroll view that follows the newest line unless
            // you've scrolled up (scroll back to the bottom to follow again). The wheel scrolls it.
            float w = rect.width - 24;
            float headerH = Math.Min(style.CalcHeight(new UnityEngine.GUIContent(text), w), rect.height - 30);
            UnityEngine.GUI.Label(new UnityEngine.Rect(12, 8, w, headerH), text, style);
            float top = 8 + headerH + 6;
            UnityEngine.GUI.DrawTexture(new UnityEngine.Rect(12, top - 3, w, 1), gripTexture);
            UnityEngine.Rect view = new UnityEngine.Rect(12, top, w, Math.Max(0, rect.height - top - 10));
            if (view.height > style.fontSize && !string.IsNullOrEmpty(log))
            {
                float inner = w - 18;  // room for the vertical scrollbar
                if (!ReferenceEquals(logHeightFor, log) || logHeightWidth != inner || logHeightFont != style.fontSize)
                {
                    logHeight = style.CalcHeight(new UnityEngine.GUIContent(log), inner);
                    logHeightFor = log; logHeightWidth = inner; logHeightFont = style.fontSize;
                }
                float maxY = Math.Max(0, logHeight - view.height);
                if (stickToBottom) scroll.y = maxY;
                scroll = UnityEngine.GUI.BeginScrollView(view, scroll, new UnityEngine.Rect(0, 0, inner, logHeight), false, true);
                UnityEngine.GUI.Label(new UnityEngine.Rect(0, 0, inner, logHeight), log, style);
                UnityEngine.GUI.EndScrollView();
                stickToBottom = scroll.y >= maxY - 4;
            }
            // The grip: a small stepped triangle in the bottom-right corner.
            for (int i = 0; i < 3; i++)
            {
                float s = 4 + 4 * i;
                UnityEngine.GUI.DrawTexture(new UnityEngine.Rect(rect.width - 4 - s, rect.height - 4 - (4 * (3 - i)) + 0, s, 3), gripTexture);
            }
            // Mouse events reach windows before the code around them, so the grip is checked here, ahead
            // of the drag: a press on it starts a resize instead. The resize itself follows the mouse in
            // Update, so it keeps going when the pointer moves outside the window.
            UnityEngine.Event e = UnityEngine.Event.current;
            UnityEngine.Rect grip = new UnityEngine.Rect(rect.width - Grip, rect.height - Grip, Grip, Grip);
            if (e.type == UnityEngine.EventType.MouseDown && e.button == 0 && grip.Contains(e.mousePosition))
            {
                resizing = true;
                resizeStart = MouseGui();
                resizeStartSize = new UnityEngine.Vector2(rect.width, rect.height);
                e.Use();
            }
            if (!resizing) UnityEngine.GUI.DragWindow();
        }

        // The mouse in GUI coordinates (top-left origin).
        private static UnityEngine.Vector2 MouseGui()
        {
            UnityEngine.InputSystem.Mouse mouse = UnityEngine.InputSystem.Mouse.current;
            if (mouse == null) return UnityEngine.Vector2.zero;
            UnityEngine.Vector2 p = mouse.position.ReadValue();
            return new UnityEngine.Vector2(p.x, UnityEngine.Screen.height - p.y);
        }

        private static void FollowResize()
        {
            if (!resizing) return;
            UnityEngine.InputSystem.Mouse mouse = UnityEngine.InputSystem.Mouse.current;
            if (mouse == null || !mouse.leftButton.isPressed) { resizing = false; return; }
            UnityEngine.Vector2 m = MouseGui();
            rect.width = resizeStartSize.x + m.x - resizeStart.x;
            rect.height = resizeStartSize.y + m.y - resizeStart.y;
            Clamp();
        }
    }

    // Turns brain answers into entries in the game's key queue.
    public static class KeyInput
    {
        // "a", "A" (shift), "Escape", "Keypad8", "ctrl+s", "shift+Tab", "alt+x"... Unity KeyCode names.
        public static string PushKey(string spec)
        {
            bool shift = false, ctrl = false, alt = false;
            string name = spec;
            while (true)
            {
                int plus = name.IndexOf('+');
                if (plus <= 0 || plus == name.Length - 1) break;
                string mod = name.Substring(0, plus).ToLowerInvariant();
                if (mod == "shift") shift = true;
                else if (mod == "ctrl") ctrl = true;
                else if (mod == "alt") alt = true;
                else break;
                name = name.Substring(plus + 1);
            }

            KeyCode code;
            char ch = '\0';
            if (name.Length == 1 && char.IsLetter(name[0]))
            {
                if (char.IsUpper(name[0])) shift = true;
                code = (KeyCode)Enum.Parse(typeof(KeyCode), name.ToUpperInvariant());
                ch = shift ? char.ToUpperInvariant(name[0]) : char.ToLowerInvariant(name[0]);
            }
            else if (name.Length == 1 && char.IsDigit(name[0]))
            {
                code = (KeyCode)Enum.Parse(typeof(KeyCode), "Alpha" + name);
                ch = name[0];
            }
            else
            {
                try { code = (KeyCode)Enum.Parse(typeof(KeyCode), name, true); }
                catch { return "unknown key '" + spec + "'"; }
                if (code == KeyCode.Space) ch = ' ';
                else if (code == KeyCode.Return || code == KeyCode.KeypadEnter) ch = '\r';
            }

            Keyboard.XRLKeyEvent ev = new Keyboard.XRLKeyEvent(code, ch, shift, ctrl, alt);
            Bot.Injecting = true;
            try { Keyboard.PushKey(ev, true); }
            finally { Bot.Injecting = false; }
            return null;
        }

        public static void PushCommand(string command)
        {
            Bot.Injecting = true;
            try { Keyboard.PushCommand(command, null); }
            finally { Bot.Injecting = false; }
        }
    }

    // What the player can see, as JSON.
    public static class Snapshot
    {
        public static string LastScreenText = "";

        // The console font is code page 437, and the buffer stores its upper half as chars 128-255.
        // This maps them to the Unicode characters they draw (box lines, shading, accented letters).
        // CP437's symbols for 0-31 (game objects can use these as glyphs, e.g. 9 is a ring).
        private const string Cp437Lower = "\u0020\u263a\u263b\u2665\u2666\u2663\u2660\u2022\u25d8\u25cb\u25d9\u2642\u2640\u266a\u266b\u263c\u25ba\u25c4\u2195\u203c\u00b6\u00a7\u25ac\u21a8\u2191\u2193\u2192\u2190\u221f\u2194\u25b2\u25bc";
        private const string Cp437Upper = "\u00c7\u00fc\u00e9\u00e2\u00e4\u00e0\u00e5\u00e7\u00ea\u00eb\u00e8\u00ef\u00ee\u00ec\u00c4\u00c5\u00c9\u00e6\u00c6\u00f4\u00f6\u00f2\u00fb\u00f9\u00ff\u00d6\u00dc\u00a2\u00a3\u00a5\u20a7\u0192\u00e1\u00ed\u00f3\u00fa\u00f1\u00d1\u00aa\u00ba\u00bf\u2310\u00ac\u00bd\u00bc\u00a1\u00ab\u00bb\u2591\u2592\u2593\u2502\u2524\u2561\u2562\u2556\u2555\u2563\u2551\u2557\u255d\u255c\u255b\u2510\u2514\u2534\u252c\u251c\u2500\u253c\u255e\u255f\u255a\u2554\u2569\u2566\u2560\u2550\u256c\u2567\u2568\u2564\u2565\u2559\u2558\u2552\u2553\u256b\u256a\u2518\u250c\u2588\u2584\u258c\u2590\u2580\u03b1\u00df\u0393\u03c0\u03a3\u03c3\u00b5\u03c4\u03a6\u0398\u03a9\u03b4\u221e\u03c6\u03b5\u2229\u2261\u00b1\u2265\u2264\u2320\u2321\u00f7\u2248\u00b0\u2219\u00b7\u221a\u207f\u00b2\u25a0\u00a0";

        public static string Build(string mode)
        {
            Bot.Sequence++;
            StringBuilder sb = new StringBuilder(8192);
            sb.Append("{\"seq\":").Append(Bot.Sequence);
            sb.Append(",\"mode\":").Append(Json.Str(mode));
            sb.Append(",\"wait\":").Append(Json.Str(Bot.WaitKind));
            try
            {
                bool active = XRL.World.Capabilities.AutoAct.IsActive(false);
                sb.Append(",\"autoact\":").Append(active ? Json.Str(XRL.World.Capabilities.AutoAct.Setting ?? "") : "null");
            }
            catch { }
            sb.Append(",\"time\":").Append(Json.Str(DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fff")));
            try { sb.Append(",\"turn\":").Append(XRLCore.CurrentTurn); } catch { }
            if (Bot.LastGotoFailed != null) { sb.Append(",\"goto_failed\":").Append(Json.Str(Bot.LastGotoFailed)); Bot.LastGotoFailed = null; }
            // Which run this is (the save folder's ID), so the brain can keep a world file per run.
            try
            {
                if (The.Game != null)
                    sb.Append(",\"game\":{\"id\":").Append(Json.Str(The.Game.GameID)).Append(",\"mode\":").Append(Json.Str(The.Game.gameMode)).Append("}");
            }
            catch { }
            AppendScreen(sb);
            AppendPlayer(sb);
            AppendMap(sb);
            AppendQuests(sb);
            AppendGear(sb);
            AppendMessages(sb);
            sb.Append("}");
            return sb.ToString();
        }

        // The classic text screen: one string of characters and one of foreground colour codes per row.
        private static void AppendScreen(StringBuilder sb)
        {
            ScreenBuffer buffer = TextConsole.CurrentBuffer;
            if (buffer == null) { sb.Append(",\"screen\":null"); return; }
            int w = buffer.Width, h = buffer.Height;
            StringBuilder text = new StringBuilder((w + 2) * h);
            sb.Append(",\"screen\":{\"w\":").Append(w).Append(",\"h\":").Append(h).Append(",\"rows\":[");
            StringBuilder colors = new StringBuilder();
            for (int y = 0; y < h; y++)
            {
                StringBuilder row = new StringBuilder(w);
                colors.Append(y == 0 ? "" : ",");
                StringBuilder fg = new StringBuilder(w);
                for (int x = 0; x < w; x++)
                {
                    ConsoleChar c = buffer[x, y];
                    char ch = c == null ? ' ' : c.Char;
                    if ((ch == '\0' || ch == ' ') && c != null && !string.IsNullOrEmpty(c.Tile) && c.BackupChar != '\0') ch = c.BackupChar;
                    if (ch == '\0') ch = ' ';
                    else if (ch >= (char)128 && ch <= (char)255) ch = Cp437Upper[ch - 128];
                    else if (ch == (char)10 || ch == (char)13) ch = ' ';
                    else if (ch < (char)32) ch = Cp437Lower[ch];
                    row.Append(ch);
                    char code = ' ';
                    try { if (c != null) code = c.ForegroundCode; } catch { }
                    fg.Append(code == '\0' ? ' ' : code);
                }
                sb.Append(y == 0 ? "" : ",").Append(Json.Str(row.ToString()));
                colors.Append(Json.Str(fg.ToString()));
                text.Append(row.ToString().TrimEnd()).Append('\n');
            }
            sb.Append("],\"fg\":[").Append(colors).Append("]}");
            LastScreenText = text.ToString();
        }

        private static void AppendPlayer(StringBuilder sb)
        {
            GameObject player = null;
            try { player = The.Player; } catch { }
            if (player == null) { sb.Append(",\"player\":null"); return; }
            sb.Append(",\"player\":{");
            sb.Append("\"name\":").Append(Json.Str(Safe(delegate { return player.DisplayNameOnlyStripped; })));
            sb.Append(",\"hp\":").Append(SafeInt(delegate { return player.hitpoints; }));
            sb.Append(",\"maxhp\":").Append(SafeInt(delegate { return player.baseHitpoints; }));
            sb.Append(",\"level\":").Append(SafeInt(delegate { return player.Level; }));
            // Our own combat stats, raw like the creatures' (2026-11-24): armour, dodge, quickness, movement.
            sb.Append(",\"av\":").Append(SafeInt(delegate { return player.Stat("AV", 0); }));
            sb.Append(",\"dv\":").Append(SafeInt(delegate { return player.Stat("DV", 0); }));
            sb.Append(",\"qn\":").Append(SafeInt(delegate { return player.Stat("Speed", 0); }));
            sb.Append(",\"ms\":").Append(SafeInt(delegate { return player.Stat("MoveSpeed", 0); }));
            // Hunger and thirst as the game words them (the sidebar text is missing from some frames).
            try
            {
                XRL.World.Parts.Stomach stomach = player.GetPart<XRL.World.Parts.Stomach>();
                if (stomach != null)
                {
                    sb.Append(",\"food\":").Append(Json.Str(ConsoleLib.Console.ColorUtility.StripFormatting(stomach.FoodStatus())));
                    sb.Append(",\"water\":").Append(Json.Str(ConsoleLib.Console.ColorUtility.StripFormatting(stomach.WaterStatus())));
                }
            }
            catch { }
            // The game's current target (the sidebar shows it; targeted abilities' pickers lock onto it).
            try
            {
                GameObject target = XRL.UI.Sidebar.CurrentTarget;
                Cell tc = target != null ? target.CurrentCell : null;
                if (tc != null && player.CurrentZone != null && tc.ParentZone == player.CurrentZone)
                    sb.Append(",\"target\":{\"name\":").Append(Json.Str(target.DisplayNameOnlyStripped))
                      .Append(",\"x\":").Append(tc.X).Append(",\"y\":").Append(tc.Y).Append("}");
            }
            catch { }
            // Active effects by name (Wet, Confused...), as the player's effect list shows them.
            sb.Append(",\"effects\":[");
            try
            {
                int n = 0;
                foreach (XRL.World.Effect e in player.Effects)
                {
                    if (e == null) continue;
                    sb.Append(n++ == 0 ? "" : ",").Append(Json.Str(e.DisplayNameStripped));
                }
            }
            catch { }
            sb.Append("]");
            Cell cell = null;
            try { cell = player.CurrentCell; } catch { }
            if (cell != null)
            {
                sb.Append(",\"x\":").Append(cell.X).Append(",\"y\":").Append(cell.Y);
                Zone zone = cell.ParentZone;
                if (zone != null)
                {
                    sb.Append(",\"zone\":").Append(Json.Str(zone.ZoneID));
                    sb.Append(",\"zoneName\":").Append(Json.Str(Safe(delegate { return zone.DisplayName; })));
                }
            }
            sb.Append("}");
        }

        // The player's zone as the player knows it. The text screen can't be used for this: in tile mode
        // the map cells hold graphics, not characters. Only what the player could see is included:
        // unexplored cells are blank, remembered cells show no creatures, and objects are listed only
        // in cells visible right now.
        //   rows: one glyph per cell (the top-most object's character, '.' for open ground)
        //   vis:  '1' visible now, '0' remembered, ' ' unexplored
        //   objects: creatures, takeable items, doors and stairs in visible cells, without the player
        private static void AppendMap(StringBuilder sb)
        {
            GameObject player = null;
            Zone zone = null;
            try { player = The.Player; zone = player.CurrentZone; } catch { }
            if (zone == null) { sb.Append(",\"map\":null"); return; }
            int w = zone.Width, h = zone.Height;
            StringBuilder objects = new StringBuilder();
            int objectCount = 0;
            // (v0.28) Features are gathered with their distance from the player and written nearest first, so a cap
            // never drops the cells round us (2026-11-27: at 300, deep water next to the player went
            // missing in a busy marsh zone). The world map (zone ID without dots, e.g. "JoppaWorld") shows
            // all its cells at once.
            List<KeyValuePair<int, string>> featureList = new List<KeyValuePair<int, string>>();
            int featureCount = 0;
            int featureCap = zone.ZoneID != null && zone.ZoneID.IndexOf('.') < 0 ? 2500 : 1200;
            int pcx = 0, pcy = 0;
            try { pcx = player.CurrentCell.X; pcy = player.CurrentCell.Y; } catch { }
            sb.Append(",\"map\":{\"w\":").Append(w).Append(",\"h\":").Append(h).Append(",\"rows\":[");
            StringBuilder visRows = new StringBuilder();
            for (int y = 0; y < h; y++)
            {
                StringBuilder row = new StringBuilder(w);
                StringBuilder vis = new StringBuilder(w);
                for (int x = 0; x < w; x++)
                {
                    char glyph = ' ';
                    char v = ' ';
                    try
                    {
                        if (zone.GetExplored(x, y))
                        {
                            bool visible = zone.GetVisibility(x, y);
                            v = visible ? '1' : '0';
                            Cell cell = zone.GetCell(x, y);
                            GameObject top = null;
                            int topLayer = int.MinValue;
                            foreach (GameObject o in cell.Objects)
                            {
                                if (o == null || o.Render == null) continue;
                                if (!visible && o.IsCreature) continue;
                                if (string.IsNullOrEmpty(o.Render.RenderString)) continue;
                                if (o.Render.RenderLayer >= topLayer) { top = o; topLayer = o.Render.RenderLayer; }
                                if (visible && objectCount < 80 && o != player
                                    && (o.IsCreature || o.IsTakeable() || o.IsDoor() || o.HasPart("StairsUp") || o.HasPart("StairsDown")))
                                {
                                    objects.Append(objectCount == 0 ? "" : ",");
                                    objects.Append("{\"x\":").Append(x).Append(",\"y\":").Append(y);
                                    objects.Append(",\"glyph\":").Append(Json.Str(Glyph(o).ToString()));
                                    objects.Append(",\"name\":").Append(Json.Str(o.DisplayNameOnlyStripped));
                                    if (o.IsCreature)
                                    {
                                        // The game's own unique id (2026-11-25, the user: reference creatures by id;
                                        // names collapse every "wet glowpad" in a zone into one record).
                                        GameObject idOf = o;
                                        objects.Append(",\"id\":").Append(Json.Str(Safe(delegate { return idOf.ID; })));
                                        objects.Append(",\"creature\":true,\"hostile\":").Append(o.IsHostileTowards(player) ? "true" : "false");
                                        // Combat facts (2026-11-24, after the tortoise fight): whether the player can
                                        // actually see it (a camouflaged lurker sits in a visible cell but isn't seen),
                                        // its armour, dodge, health, resistances, effects and mutations.
                                        try
                                        {
                                            objects.Append(",\"seen\":").Append(o.IsVisible() ? "true" : "false");
                                            objects.Append(",\"av\":").Append(o.Stat("AV", 0)).Append(",\"dv\":").Append(o.Stat("DV", 0));
                                            // Speed (quickness: actions) and MoveSpeed (movement), raw stats, and level
                                            // (2026-11-24: kite what is slower than us; judge danger live).
                                            objects.Append(",\"qn\":").Append(o.Stat("Speed", 0)).Append(",\"ms\":").Append(o.Stat("MoveSpeed", 0)).Append(",\"lvl\":").Append(o.Stat("Level", 0));
                                            // Its offence, read before it ever hits us (2026-11-24, after a hulking baboon
                                            // bit for 9 twice): the game's own difficulty word (what Look shows), its
                                            // Strength and Agility modifiers, and every melee attack it has (wielded or
                                            // natural): damage dice, penetration bonus, strength cap, hit bonus.
                                            try
                                            {
                                                string dd = XRL.World.Capabilities.DifficultyEvaluation.GetDifficultyDescription(o, player, null, true);
                                                if (!string.IsNullOrEmpty(dd)) objects.Append(",\"diff\":").Append(Json.Str(dd));
                                            }
                                            catch { }
                                            objects.Append(",\"str\":").Append(o.StatMod("Strength", 0)).Append(",\"agi\":").Append(o.StatMod("Agility", 0));
                                            try
                                            {
                                                StringBuilder at = new StringBuilder();
                                                HashSet<GameObject> seenWeapons = new HashSet<GameObject>();
                                                if (o.Body != null)
                                                {
                                                    foreach (XRL.World.Anatomy.BodyPart bp in o.Body.GetParts())
                                                    {
                                                        GameObject[] candidates = { bp.Equipped, bp.DefaultBehavior };
                                                        foreach (GameObject cw in candidates)
                                                        {
                                                            if (cw == null || seenWeapons.Contains(cw)) continue;
                                                            XRL.World.Parts.MeleeWeapon mw = cw.GetPart<XRL.World.Parts.MeleeWeapon>();
                                                            if (mw == null || string.IsNullOrEmpty(mw.BaseDamage)) continue;
                                                            seenWeapons.Add(cw);
                                                            at.Append(at.Length == 0 ? "" : ",");
                                                            at.Append("{\"name\":").Append(Json.Str(cw.DisplayNameOnlyStripped));
                                                            at.Append(",\"dmg\":").Append(Json.Str(mw.BaseDamage));
                                                            at.Append(",\"pen\":").Append(mw.PenBonus).Append(",\"cap\":").Append(mw.MaxStrengthBonus);
                                                            at.Append(",\"hit\":").Append(mw.HitBonus).Append(",\"part\":").Append(Json.Str(bp.Type)).Append("}");
                                                            break;
                                                        }
                                                    }
                                                }
                                                if (at.Length > 0) objects.Append(",\"attacks\":[").Append(at.ToString()).Append("]");
                                            }
                                            catch { }
                                            // Its parts (what it can do beyond melee: BurstOnDeath, SplitOnDeath,
                                            // ExplodeOnHit...) and its description text (2026-11-24: a tumbling pod's
                                            // explosion on death killed us; the estimate only saw its weak attacks).
                                            try
                                            {
                                                string boring = "|Render|Physics|Description|Brain|Body|Combat|Inventory|Stomach|Corpse|Experience|Leveler|Mutations|Skills|ActivatedAbilities|DisplayNameColor|RandomLoot|Interesting|Commerce|Lair|Statistic|Hidden|Faction|Gender|Pronouns|ConversationScript|Chat|Spawner|MentalShield|Armor|MeleeWeapon|";
                                                StringBuilder pt = new StringBuilder();
                                                int pc = 0;
                                                foreach (XRL.World.IPart ip in o.PartsList)
                                                {
                                                    if (ip == null) continue;
                                                    string pn = ip.GetType().Name;
                                                    if (boring.Contains("|" + pn + "|")) continue;
                                                    pt.Append(pc == 0 ? "" : ",").Append(Json.Str(pn));
                                                    if (++pc >= 40) break;
                                                }
                                                if (pc > 0) objects.Append(",\"parts\":[").Append(pt.ToString()).Append("]");
                                                XRL.World.Parts.Description dp = o.GetPart<XRL.World.Parts.Description>();
                                                if (dp != null)
                                                {
                                                    string sd = dp.Short;
                                                    if (!string.IsNullOrEmpty(sd)) objects.Append(",\"desc\":").Append(Json.Str(sd.Length > 300 ? sd.Substring(0, 300) : sd));
                                                }
                                            }
                                            catch { }
                                            XRL.World.Statistic hp = o.GetStat("Hitpoints");
                                            if (hp != null) objects.Append(",\"hp\":").Append(hp.Value).Append(",\"maxhp\":").Append(hp.BaseValue);
                                            string[] resists = { "HeatResistance", "ColdResistance", "ElectricResistance", "AcidResistance" };
                                            string[] keys = { "heat", "cold", "elec", "acid" };
                                            StringBuilder r = new StringBuilder();
                                            for (int i = 0; i < resists.Length; i++)
                                            {
                                                int rv = o.Stat(resists[i], 0);
                                                if (rv != 0) r.Append(r.Length == 0 ? "" : ",").Append("\"").Append(keys[i]).Append("\":").Append(rv);
                                            }
                                            if (r.Length > 0) objects.Append(",\"resist\":{").Append(r.ToString()).Append("}");
                                            StringBuilder eff = new StringBuilder();
                                            foreach (XRL.World.Effect e in o.Effects)
                                            {
                                                string n = e.DisplayNameStripped;
                                                if (string.IsNullOrEmpty(n)) continue;
                                                eff.Append(eff.Length == 0 ? "" : ",").Append(Json.Str(n));
                                            }
                                            if (eff.Length > 0) objects.Append(",\"effects\":[").Append(eff.ToString()).Append("]");
                                            List<string> muts = o.GetMutationNames();
                                            if (muts != null && muts.Count > 0)
                                            {
                                                objects.Append(",\"mutations\":[");
                                                for (int i = 0; i < muts.Count; i++) objects.Append(i == 0 ? "" : ",").Append(Json.Str(muts[i]));
                                                objects.Append("]");
                                            }
                                        }
                                        catch { }
                                    }
                                    objects.Append("}");
                                    objectCount++;
                                }
                                // Terrain and features in view by name: pools (with their liquid),
                                // furniture, plants, and on the world map each cell's terrain. Walls
                                // and everything already in objects are left out.
                                else if (visible && featureCount < 4000 && o != player && !o.IsCreature && !o.IsTakeable()
                                    && !o.IsDoor() && !o.IsWall() && !o.HasPart("StairsUp") && !o.HasPart("StairsDown"))
                                {
                                    StringBuilder one = new StringBuilder();
                                    one.Append("{\"x\":").Append(x).Append(",\"y\":").Append(y);
                                    one.Append(",\"name\":").Append(Json.Str(o.DisplayNameStripped)).Append("}");
                                    int d = Math.Max(Math.Abs(x - pcx), Math.Abs(y - pcy));
                                    featureList.Add(new KeyValuePair<int, string>(d, one.ToString()));
                                    featureCount++;
                                }
                            }
                            glyph = top == null ? '.' : Glyph(top);
                        }
                    }
                    catch { glyph = '?'; }
                    row.Append(glyph);
                    vis.Append(v);
                }
                sb.Append(y == 0 ? "" : ",").Append(Json.Str(row.ToString()));
                visRows.Append(y == 0 ? "" : ",").Append(Json.Str(vis.ToString()));
            }
            featureList.Sort((a, b) => a.Key.CompareTo(b.Key));
            StringBuilder features = new StringBuilder();
            for (int i = 0; i < featureList.Count && i < featureCap; i++)
                features.Append(i == 0 ? "" : ",").Append(featureList[i].Value);
            sb.Append("],\"vis\":[").Append(visRows).Append("],\"objects\":[").Append(objects)
              .Append("],\"features\":[").Append(features).Append("]}");
        }

        private static char Glyph(GameObject o)
        {
            string s = o.Render.RenderString;
            if (string.IsNullOrEmpty(s)) return '?';
            char c = s[0];
            if (c >= (char)128 && c <= (char)255) c = Cp437Upper[c - 128];
            else if (c == (char)10 || c == (char)13) c = ' ';
            else if (c < (char)32) c = Cp437Lower[c];
            return c == ' ' ? '.' : c;
        }

        // The quest log as the player sees it: open and finished quests, with their visible steps.
        private static void AppendQuests(StringBuilder sb)
        {
            sb.Append(",\"quests\":[");
            int n = 0;
            try
            {
                n = AppendQuestMap(sb, The.Game.Quests, n);
                n = AppendQuestMap(sb, The.Game.FinishedQuests, n);
            }
            catch (Exception ex) { sb.Append(n == 0 ? "" : ",").Append(Json.Str("error: " + ex.Message)); }
            sb.Append("]");
        }

        private static int AppendQuestMap(StringBuilder sb, XRL.Collections.StringMap<Quest> quests, int n)
        {
            if (quests == null) return n;
            foreach (Quest q in quests.Values)
            {
                if (q == null) continue;
                sb.Append(n++ == 0 ? "" : ",");
                sb.Append("{\"name\":").Append(Json.Str(ConsoleLib.Console.ColorUtility.StripFormatting(q.DisplayName ?? q.Name)));
                sb.Append(",\"finished\":").Append(q.Finished ? "true" : "false");
                sb.Append(",\"giver\":").Append(Json.Str(q.QuestGiverName));
                sb.Append(",\"where\":").Append(Json.Str(q.QuestGiverLocationName));
                sb.Append(",\"steps\":[");
                int s = 0;
                if (q.StepsByID != null)
                {
                    foreach (QuestStep step in q.StepsByID.Values)
                    {
                        if (step == null || step.Hidden) continue;
                        sb.Append(s++ == 0 ? "" : ",");
                        sb.Append("{\"name\":").Append(Json.Str(ConsoleLib.Console.ColorUtility.StripFormatting(step.Name)));
                        sb.Append(",\"text\":").Append(Json.Str(ConsoleLib.Console.ColorUtility.StripFormatting(step.Text)));
                        sb.Append(",\"finished\":").Append(step.Finished ? "true" : "false");
                        if (step.Failed) sb.Append(",\"failed\":true");
                        if (step.Optional) sb.Append(",\"optional\":true");
                        sb.Append("}");
                    }
                }
                sb.Append("]}");
            }
            return n;
        }

        // What the player carries and wears, by the full names the game shows ("lit torch",
        // "waterskin [24 drams of fresh water]"...).
        private static void AppendGear(StringBuilder sb)
        {
            sb.Append(",\"inventory\":[");
            try
            {
                List<GameObject> items = The.Player.Inventory.GetObjects();
                for (int i = 0; i < items.Count; i++)
                    sb.Append(i == 0 ? "" : ",").Append(Json.Str(items[i].DisplayNameStripped));
            }
            catch { }
            sb.Append("],\"equipped\":[");
            try
            {
                List<GameObject> worn = The.Player.Body.GetEquippedObjects();
                for (int i = 0; i < worn.Count; i++)
                    sb.Append(i == 0 ? "" : ",").Append(Json.Str(worn[i].DisplayNameStripped));
            }
            catch { }
            // The game's own ids, in the same order as the two lists above (v0.27, 2026-11-26: the user,
            // reference items by id as we do creatures; weapon records were pooled by name).
            sb.Append("],\"inventory_ids\":[");
            try
            {
                List<GameObject> items = The.Player.Inventory.GetObjects();
                for (int i = 0; i < items.Count; i++)
                {
                    GameObject it = items[i];
                    sb.Append(i == 0 ? "" : ",").Append(Json.Str(Safe(delegate { return it.ID; })));
                }
            }
            catch { }
            sb.Append("],\"equipped_ids\":[");
            try
            {
                List<GameObject> worn = The.Player.Body.GetEquippedObjects();
                for (int i = 0; i < worn.Count; i++)
                {
                    GameObject it = worn[i];
                    sb.Append(i == 0 ? "" : ",").Append(Json.Str(Safe(delegate { return it.ID; })));
                }
            }
            catch { }
            sb.Append("]");
        }

        private static void AppendMessages(StringBuilder sb)
        {
            sb.Append(",\"messages\":[");
            try
            {
                List<string> all = The.Game.Player.Messages.Messages;
                int start = Math.Max(0, all.Count - 15);
                for (int i = start; i < all.Count; i++)
                {
                    sb.Append(i == start ? "" : ",").Append(Json.Str(ConsoleLib.Console.ColorUtility.StripFormatting(all[i])));
                }
            }
            catch { }
            sb.Append("]");
        }

        private delegate string StringGetter();
        private delegate int IntGetter();
        private static string Safe(StringGetter get) { try { return get(); } catch { return null; } }
        private static string SafeInt(IntGetter get) { try { return get().ToString(); } catch { return "null"; } }
    }

    public static class Json
    {
        public static string Str(string s)
        {
            if (s == null) return "null";
            StringBuilder sb = new StringBuilder(s.Length + 2);
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
            return sb.ToString();
        }
    }

    // The map loop (XRLCore.PlayerTurn) sleeps while GameManager.focused is false, so with the game
    // window in the background no turn is played. During a bot run the game is told it's focused, so
    // the bot can play while the player (or the LLM's terminal) has another window in front.
    [HarmonyPatch(typeof(GameManager), "get_focused")]
    public static class FocusPatch
    {
        public static void Postfix(ref bool __result)
        {
            if (Bot.Running || Bot.StepRequested) __result = true;
        }
    }

    // On the map the game doesn't block in GetNextKey: XRLCore.PlayerTurn loops "key waiting? if not,
    // Keyboard.IdleWait()" and only calls GetNextKey once a key is queued. So the bot also gets its turn
    // here, just before each idle wait. (Look mode idles here too.)
    [HarmonyPatch(typeof(Keyboard), "IdleWait")]
    public static class IdleWaitPatch
    {
        public static void Prefix()
        {
            Bot.WaitKind = "map";
            try { GetNextKeyPatch.Prefix(); }
            finally { Bot.WaitKind = "key"; }
        }
    }

    // Before the game waits for a key (menus, popups): let the bot add keys to the queue first.
    [HarmonyPatch(typeof(Keyboard), "GetNextKey")]
    public static class GetNextKeyPatch
    {
        public static void Prefix()
        {
            try { Bot.OnKeyWait(); }
            catch (Exception ex)
            {
                Bot.Running = false;
                UnityEngine.Debug.LogError("QudBot: " + ex);
                Bot.AppendLog("{\"kind\":\"exception\",\"error\":" + Json.Str(ex.ToString()) + "}");
            }
        }
    }

    // The control keys are read straight from the keyboard every frame, on Unity's thread. They can't
    // be caught where keys enter the game's queue: keys the game has bindings for (F1 is Help) arrive
    // there as commands instead (see DropControlCommands). After a control key the mod pushes
    // WakeKey, which the game ignores, but whose arrival lets a waiting GetNextKey return and be
    // called again, which is when the bot acts. During a run, any other key press stops it.
    [HarmonyPatch(typeof(GameManager), "UpdateInput")]
    public static class ControlKeysPatch
    {
        // While the game window isn't focused, the game's own keyboard/mouse handling is skipped. Running
        // in the background (for the bot and the user's option) leaves the Input System listening to
        // the keyboard globally, so typing in another window turned into game commands (2026-11-24).
        // The bot doesn't go through here: it pushes into the game's queue directly. The postfix still
        // runs (Harmony runs postfixes after a skipped original).
        // Clicks on the bot panel (dragging, resizing) are also skipped, so they don't reach the map.
        public static bool Prefix()
        {
            if (!UnityEngine.Application.isFocused) return false;
            try { if (BotPanel.ShouldBlockInput()) return false; } catch { }
            return true;
        }

        private static bool heartbeat;
        private static int optionCheckFrame = -1000;
        private static bool backgroundOption;

        // Unity stops its frame loop when the window loses focus, and a zone change waits on that loop,
        // so with the game in the background the bot stalled at every zone edge (2026-11-24). During a
        // run Unity keeps running in the background. Otherwise the game's own option decides
        // ("Keep Caves of Qud active in background", OptionMusicBackground): the mod used to restore the
        // value from startup, which overrode that option between runs.
        private static void KeepRunningInBackground()
        {
            if (UnityEngine.Time.frameCount - optionCheckFrame > 60)
            {
                optionCheckFrame = UnityEngine.Time.frameCount;
                try { backgroundOption = XRL.UI.Options.GetOption("OptionMusicBackground", "No") == "Yes"; } catch { }
            }
            bool want = Bot.Running || backgroundOption;
            if (UnityEngine.Application.runInBackground != want) UnityEngine.Application.runInBackground = want;
        }

        public static void Postfix()
        {
            try
            {
                UnityEngine.InputSystem.Keyboard kb = UnityEngine.InputSystem.Keyboard.current;
                if (!heartbeat)
                {
                    heartbeat = true;
                    Bot.AppendLog("{\"kind\":\"heartbeat\",\"keyboard\":" + (kb != null ? "true" : "false") + "}");
                }
                AutoStartRun();
                bool focusedNow = UnityEngine.Application.isFocused;
                if (focusedNow && !wasFocused) focusGainedMs = Clock.ElapsedMilliseconds;
                wasFocused = focusedNow;
                KeepRunningInBackground();
                BotPanel.Ensure();
                if (kb == null || !focusedNow) return;  // control keys only count with the game focused
                if (kb[UnityEngine.InputSystem.Key.F10].wasPressedThisFrame) BotPanel.Visible = !BotPanel.Visible;
                // F9: the narrator's voice on/off (live/voice_on; tools/narrator.ps1 reads live/voice.log aloud).
                if (kb[UnityEngine.InputSystem.Key.F9].wasPressedThisFrame)
                {
                    try
                    {
                        string flag = Path.Combine(Bot.LiveDir, "voice_on");
                        if (File.Exists(flag)) { File.Delete(flag); Bot.Say("voice off"); }
                        else { File.WriteAllText(flag, "on"); Bot.Say("voice on"); }
                    }
                    catch { }
                }
                if (kb[Bot.RunInputKey].wasPressedThisFrame) Control("run", "poll");
                else if (kb[Bot.StepInputKey].wasPressedThisFrame) Control("step", "poll");
                else if (kb[Bot.ReportInputKey].wasPressedThisFrame) Control("report", "poll");
                else if (Bot.Running && kb.anyKey.wasPressedThisFrame && UnityEngine.Application.isFocused
                    && Clock.ElapsedMilliseconds - focusGainedMs > 500 && NonModifierPressed(kb))
                {
                    Bot.StopRequested = true;
                    Bot.AppendLog("{\"kind\":\"stopkey\"}");
                }
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogError("QudBot: " + ex);
            }
        }

        // auto_start (bridge.json): once per game id, when the player has been standing in a zone on two
        // checks about half a second apart (so never during character creation), start a run as if F1
        // had been pressed. Stopping it with F1 keeps it stopped for that game.
        private static string autoStartedGame = null;
        private static string autoSeenGame = null;
        private static int autoCheckFrame = -1000;
        private static void AutoStartRun()
        {
            if (UnityEngine.Time.frameCount - autoCheckFrame < 30) return;
            autoCheckFrame = UnityEngine.Time.frameCount;
            Config.Refresh();
            if (!Config.AutoStart || Bot.Running) { autoSeenGame = null; return; }
            string id = null;
            try
            {
                if (The.Game != null && The.Player != null && The.Player.CurrentZone != null) id = The.Game.GameID;
            }
            catch { id = null; }
            if (id == null || id == autoStartedGame) { autoSeenGame = null; return; }
            if (autoSeenGame != id) { autoSeenGame = id; return; }  // seen once; start on the next check
            autoStartedGame = id;
            autoSeenGame = null;
            Bot.CallsThisRun = 0;
            Bot.Running = true;
            Bot.PendingSay = "Bot: run started automatically (F1 or any key stops it).";
            Bot.AppendLog("{\"kind\":\"control\",\"key\":\"run\",\"via\":\"auto_start\",\"running\":true}");
            Wake();
        }

        private static readonly Stopwatch Clock = Stopwatch.StartNew();
        private static long lastControlMs = -1000;
        // Coming back to the window can report a key press (the one that switched windows); ignore
        // presses for a moment after focus returns, so it doesn't stop a run.
        private static bool wasFocused = true;
        private static long focusGainedMs = -1000;

        // A control key can be seen twice (by the frame poll and as a raw key); one press = one action.
        public static void Control(string which, string via)
        {
            long now = Clock.ElapsedMilliseconds;
            if (now - lastControlMs < 250) return;
            lastControlMs = now;
            if (which == "run")
            {
                // Stopping is announced by Bot.Stop; starting is announced here, so every F1 shows
                // something in the message log.
                if (Bot.Running) Bot.StopRequested = true;
                else { Bot.CallsThisRun = 0; Bot.Running = true; Bot.PendingSay = "Bot: run started (F1 or any key stops it)."; }
            }
            else if (which == "step") { Bot.StepRequested = true; Bot.PendingSay = "Bot: one step."; }
            else if (which == "report") Bot.ReportRequested = true;
            Bot.AppendLog("{\"kind\":\"control\",\"key\":" + Json.Str(which) + ",\"via\":" + Json.Str(via)
                + ",\"running\":" + (Bot.Running ? "true" : "false") + "}");
            Wake();
        }

        // Alt, Ctrl, Shift, Windows and Tab don't stop a run, so switching windows (Alt+Tab) is safe.
        private static bool NonModifierPressed(UnityEngine.InputSystem.Keyboard kb)
        {
            foreach (UnityEngine.InputSystem.Controls.KeyControl k in kb.allKeys)
            {
                if (k == null || !k.wasPressedThisFrame) continue;
                switch (k.keyCode)
                {
                    case UnityEngine.InputSystem.Key.LeftAlt: case UnityEngine.InputSystem.Key.RightAlt:
                    case UnityEngine.InputSystem.Key.LeftCtrl: case UnityEngine.InputSystem.Key.RightCtrl:
                    case UnityEngine.InputSystem.Key.LeftShift: case UnityEngine.InputSystem.Key.RightShift:
                    case UnityEngine.InputSystem.Key.LeftMeta: case UnityEngine.InputSystem.Key.RightMeta:
                    case UnityEngine.InputSystem.Key.Tab: case UnityEngine.InputSystem.Key.ContextMenu:
                        continue;
                }
                return true;
            }
            return false;
        }

        public static bool ControlKeyHeld()
        {
            UnityEngine.InputSystem.Keyboard kb = UnityEngine.InputSystem.Keyboard.current;
            return kb != null && (kb[Bot.RunInputKey].isPressed || kb[Bot.StepInputKey].isPressed || kb[Bot.ReportInputKey].isPressed);
        }

        private static void Wake()
        {
            Bot.Injecting = true;
            try { Keyboard.PushKey(new Keyboard.XRLKeyEvent(Bot.WakeKey, '\0', false, false, false), true); }
            finally { Bot.Injecting = false; }
        }
    }

    // Keeps the game from also acting on a control key: drops its raw key, and the commands it is
    // bound to (Help, target lock for F1) while it is held. During a run, other raw keys are dropped
    // too, so the key that stops a run doesn't also act.
    [HarmonyPatch(typeof(Keyboard), "PushKey", new Type[] { typeof(Keyboard.XRLKeyEvent), typeof(bool) })]
    public static class DropControlKeys
    {
        public static bool Prefix(Keyboard.XRLKeyEvent ev)
        {
            if (Bot.Injecting || ev == null) return true;
            if (ev.keyCode == Bot.RunKey) { ControlKeysPatch.Control("run", "key"); return false; }
            if (ev.keyCode == Bot.StepKey) { ControlKeysPatch.Control("step", "key"); return false; }
            if (ev.keyCode == Bot.ReportKey) { ControlKeysPatch.Control("report", "key"); return false; }
            if (Bot.Running) return false;
            return true;
        }
    }

    // Cell pickers (Move to, throwing, targeting) loop on Keyboard.kbhit() and only read a key once one
    // is waiting, so neither GetNextKey nor IdleWait gives the bot a turn there. While a picker is open,
    // kbhit does (wait kind "picker"). kbhit is polled in many other places, so only inside pickers.
    [HarmonyPatch(typeof(XRL.UI.PickTarget), "ShowPicker")]
    public static class PickerPatch
    {
        [ThreadStatic] public static int Depth;
        [ThreadStatic] private static bool aimed;
        // AIM x y (2026-11-24): return that cell straight away instead of showing the picker. The game
        // still applies its own rules to the cell (range, line of fire, a teleport's uncertainty).
        public static bool Prefix(ref XRL.World.Cell __result)
        {
            aimed = false;
            if (Bot.AimX >= 0 && Bot.AimY >= 0)
            {
                try
                {
                    XRL.World.Zone z = The.Player != null ? The.Player.CurrentZone : null;
                    XRL.World.Cell c = z != null ? z.GetCell(Bot.AimX, Bot.AimY) : null;
                    Bot.AimX = -1; Bot.AimY = -1;
                    if (c != null) { __result = c; aimed = true; return false; }
                }
                catch { Bot.AimX = -1; Bot.AimY = -1; }
            }
            Depth++;
            return true;
        }
        public static void Finalizer() { if (aimed) { aimed = false; return; } if (Depth > 0) Depth--; }
    }

    // Missile weapons (the musket) have their own targeting loop, MissileWeapon.ShowPicker, polling kbhit
    // the same way (2026-11-24: CmdFire left the bot unasked). Counted as a picker too.
    [HarmonyPatch(typeof(XRL.World.Parts.MissileWeapon), "ShowPicker")]
    public static class MissilePickerPatch
    {
        public static void Prefix() { PickerPatch.Depth++; }
        public static void Finalizer() { if (PickerPatch.Depth > 0) PickerPatch.Depth--; }
    }

    [HarmonyPatch(typeof(Keyboard), "kbhit")]
    public static class PickerWaitPatch
    {
        public static void Prefix()
        {
            if (PickerPatch.Depth <= 0) return;
            Bot.WaitKind = "picker";
            try { GetNextKeyPatch.Prefix(); }
            finally { Bot.WaitKind = "key"; }
        }
    }

    [HarmonyPatch(typeof(Keyboard), "PushMouseEvent", new Type[] { typeof(string), typeof(object) })]
    public static class DropControlCommands
    {
        public static bool Prefix(string ev)
        {
            if (Bot.Injecting || ev == null) return true;
            if (ControlKeysPatch.ControlKeyHeld() && (ev.EndsWith("CmdHelp") || ev.EndsWith("CmdLockUnlock"))) return false;
            return true;
        }
    }
}
