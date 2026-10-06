# 🚀 Delta-V: Mission Architect

**A rocket-design game for the NASA Space Apps Challenge 2026**
Challenge: *Space Mission Design Game* · Local event: Dhaka · Team: Broken Coders

Design a two-stage rocket, launch it, and see if it can reach **Earth orbit**, **the Moon** or **Mars**. The game uses the real rocket equation, so every choice you make (engine, fuel, payload) changes the result.

---

## 🎮 Play it

| Version | How to play |
|---|---|
| 🌐 **Web (HTML/JavaScript)** | Open `html_web_version/index.html` in any browser, or play online: https://mahialaraf.github.io/NASA/html_web_version/ |
| 🪟 **Windows app (Python)** | Download `game.exe` from the [latest release](https://github.com/MahiAlAraf/NASA/releases/latest) and double-click it |
| 🐍 **Python source** | `pip install pygame` then `python python_version/game.py` |

> If Windows shows *"Windows protected your PC"*, click **More info → Run anyway**. The warning appears because the app isn't code-signed.

---

## 🕹️ How to play

1. **Pick a mission:** Orbit, Moon or Mars.
2. **Build your rocket:** choose the engine, number of engines and fuel for each of the two stages, and set the payload.
3. **Check the Design Check panel:** the thrust-to-weight ratio must be above 1, and total delta-v must be at least what the mission needs.
4. **Press LAUNCH** and watch the countdown, liftoff, stage separation and arrival.
5. **Try again:** press REDESIGN to improve your rocket.

There are four possible endings:

| Ending | Meaning |
|---|---|
| ✅ Mission success | You reached your target |
| 🛰️ Stuck in orbit | You reached orbit but not the Moon or Mars |
| 💥 Mission failed | You ran out of fuel before orbit and fell back |
| 🚫 No liftoff | The engines were too weak to lift the rocket |

---

## 🧮 The physics

Each stage adds speed according to the **Tsiolkovsky rocket equation**:

```
delta_v = Isp × 9.81 × ln(start_mass / end_mass)
```

- **Isp** is the engine's efficiency (higher is better).
- **start_mass** is the stage weight before burning, **end_mass** is the weight after the fuel is gone.
- The total delta-v of both stages must reach the target:

| Target | Delta-v needed (approx.) |
|---|---|
| Low Earth orbit | 9,400 m/s |
| The Moon | 12,500 m/s |
| Mars | 13,000 m/s |

**Worked example:** Isp = 300 s, rocket weighs 100 t of which 80 t is fuel → `ln(100 / 20) = 1.61` → `300 × 9.81 × 1.61 ≈ 4,740 m/s`.

The game also checks the **thrust-to-weight ratio** at liftoff and models **staging**: dropping the empty booster improves the mass ratio of the second stage.

---

## 📁 Repository structure

```
NASA/
├── html_web_version/   # JavaScript + HTML5 Canvas version
│   └── index.html
└── python_version/     # Python + Pygame version
    └── game.py
```

Both versions use the same physics, engine data and flight timeline.

---

## 🛠️ Built with

- **Web version:** HTML, CSS, JavaScript, Canvas API
- **Python version:** Python 3, Pygame (packaged to `.exe` with PyInstaller)

### Build the `.exe` yourself

```
pip install pygame pyinstaller
python -m PyInstaller --onefile --windowed game.py
```

The result is in the `dist/` folder.

---

## 📊 Data and credits

- Planetary data: [NASA Planetary Fact Sheet (NSSDCA)](https://nssdc.gsfc.nasa.gov/planetary/factsheet/)
- Engine specifications: [NASA Technical Reports Server (NTRS)](https://ntrs.nasa.gov/) and public figures. Engine values in the game are approximate.
- Delta-v targets are rough textbook numbers from Earth's surface.

## 👥 Team

**Broken Coders**: add your members' names here.

Made for the NASA Space Apps Challenge 2026, Dhaka. 🌍➡️🌕➡️🔴
