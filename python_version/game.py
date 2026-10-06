"""
DELTA-V: MISSION ARCHITECT  (Python + Pygame version)

Design a 2-stage rocket, launch it, and try to reach Earth orbit, the Moon or Mars.

How to run:
    pip install pygame
    python game.py

How the file is organised (same order as the JavaScript version):
    1. DATA           engines, targets, constants
    2. HELPERS        small maths and drawing helpers
    3. PHYSICS        the rocket equation, stage calculation, flight timeline
    4. UI WIDGETS     slider, selector, button (Pygame has none built in)
    5. THE APP        game state, update(), draw(), event handling
    6. START          main()

Physics: delta_v = Isp * 9.81 * ln(start_mass / end_mass)   (Tsiolkovsky rocket equation)
Data sources: NASA Planetary Fact Sheet (NSSDCA) and NASA Technical Reports Server (NTRS).
"""

import math
import random
import sys

import pygame

# =====================================================================
# 1. DATA  (edit these numbers to change the game)
# =====================================================================
# mass in tonnes, thrust in kilonewtons (kN), isp in seconds
ENGINES = [
    {
        "name": "Merlin 1D (kerosene)",
        "mass": 0.47,
        "thrust": 845,
        "isp": 300,
        "color": (154, 165, 184),
    },
    {
        "name": "Raptor (methane)",
        "mass": 1.6,
        "thrust": 2300,
        "isp": 330,
        "color": (200, 205, 214),
    },
    {
        "name": "RS-25 (hydrogen)",
        "mass": 3.5,
        "thrust": 2280,
        "isp": 440,
        "color": (183, 134, 75),
    },
    {
        "name": "RL10 (hydrogen, upper)",
        "mass": 0.3,
        "thrust": 110,
        "isp": 465,
        "color": (143, 183, 201),
    },
]

# total delta-v needed from the ground (m/s)
TARGETS = [
    {"name": "EARTH ORBIT", "short": "Orbit", "needed": 9400},
    {"name": "THE MOON", "short": "Moon", "needed": 12500},
    {"name": "MARS", "short": "Mars", "needed": 13000},
]

G0 = 9.81  # gravity constant used in the rocket equation
STRUCTURE_FRACTION = 0.08  # tank weight = 8% of the fuel weight
ORBIT_DV = 9400  # delta-v needed to reach low Earth orbit

# flight timing (seconds)
COUNTDOWN_SECONDS = 3.6
STAGE1_BURN = 6
SEPARATION_PAUSE = 1.2
STAGE2_BURN = 7

# window layout (pixels)
SCENE_W, SCENE_H = 960, 540  # the picture of the launch
TOP_BAR = 30  # title strip above the scene
BOTTOM_BAR = 30  # note strip below the scene
SCREEN_W, SCREEN_H = 1280, TOP_BAR + SCENE_H + BOTTOM_BAR
GROUND_Y = 470  # where the ground is inside the scene
ROCKET_X = 480  # horizontal centre of the rocket inside the scene

# colours
WHITE = (255, 255, 255)
YELLOW = (255, 209, 102)
GREEN = (6, 214, 160)
RED = (239, 71, 111)
BLUE = (76, 201, 240)
PANEL_BG = (18, 26, 51)
PANEL_BORDER = (31, 42, 77)
TEXT_LIGHT = (197, 206, 230)
TEXT_DIM = (143, 155, 189)
APP_BG = (7, 11, 23)


# =====================================================================
# 2. SMALL HELPERS
# =====================================================================
def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(a, b, t):
    return a + (b - a) * t


def mix_color(a, b, t):
    """Mix two (r, g, b) colours. t = 0 gives a, t = 1 gives b."""
    return (
        int(round(lerp(a[0], b[0], t))),
        int(round(lerp(a[1], b[1], t))),
        int(round(lerp(a[2], b[2], t))),
    )


def format_number(n):
    """12345.6 -> '12,346'"""
    return f"{round(n):,}"


_font_cache = {}


def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("arial", size, bold=bold)
    return _font_cache[key]


def draw_text(surface, text, pos, size, color, anchor="topleft", bold=False, alpha=255):
    """Draw text. 'anchor' says which point of the text sits at 'pos' (e.g. 'center', 'midright')."""
    image = get_font(size, bold).render(text, True, color)
    if alpha < 255:
        image.set_alpha(alpha)
    rect = image.get_rect(**{anchor: pos})
    surface.blit(image, rect)
    return rect


def draw_alpha_rect(surface, color, rect, alpha):
    """Rectangle with transparency (alpha 0-255)."""
    temp = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    temp.fill((color[0], color[1], color[2], int(alpha)))
    surface.blit(temp, (rect[0], rect[1]))


def draw_alpha_circle(surface, color, center, radius, alpha):
    """Circle with transparency (alpha 0-255)."""
    radius = max(1, int(radius))
    temp = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(
        temp, (color[0], color[1], color[2], int(alpha)), (radius, radius), radius
    )
    surface.blit(temp, (center[0] - radius, center[1] - radius))


def quad_points(p0, p1, p2, steps=14):
    """Points along a curved line (quadratic Bezier). Used for hills and the nose cone."""
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        points.append((x, y))
    return points


def blit_rotated(surface, image, pivot_on_screen, pivot_in_image, angle_degrees):
    """
    Rotate 'image' around one of its own points (the pivot) and draw it so that
    the pivot lands on 'pivot_on_screen'.
    angle_degrees > 0 turns the image counter-clockwise (that is how Pygame works).
    """
    image_center = pygame.math.Vector2(image.get_width() / 2, image.get_height() / 2)
    offset = pygame.math.Vector2(pivot_in_image) - image_center  # centre -> pivot
    rotated_offset = offset.rotate(-angle_degrees)
    rotated_image = pygame.transform.rotozoom(image, angle_degrees, 1)
    center = (
        pivot_on_screen[0] - rotated_offset.x,
        pivot_on_screen[1] - rotated_offset.y,
    )
    surface.blit(rotated_image, rotated_image.get_rect(center=center))


# =====================================================================
# 3. PHYSICS  (same maths as the JavaScript version)
# =====================================================================
def calculate_delta_v(isp, start_mass, end_mass):
    """Rocket equation: how much speed a stage can add."""
    return isp * G0 * math.log(start_mass / end_mass)


def calculate_stage(engine, engine_count, fuel_mass, mass_above):
    """
    One stage.
    mass_above = everything this stage has to carry (upper stage + payload).
    """
    dry_mass = (
        engine["mass"] * engine_count + fuel_mass * STRUCTURE_FRACTION
    )  # empty stage
    start_mass = mass_above + dry_mass + fuel_mass  # before burning
    end_mass = mass_above + dry_mass  # after burning all fuel
    return {
        "start_mass": start_mass,
        "delta_v": calculate_delta_v(engine["isp"], start_mass, end_mass),
        "total_thrust": engine["thrust"] * engine_count,
    }


def compute_design(c):
    """c = the player's choices. Returns the numbers that decide the flight."""
    stage2 = calculate_stage(c["engine2"], c["count2"], c["fuel2"], c["payload"])
    stage1 = calculate_stage(
        c["engine1"], c["count1"], c["fuel1"], stage2["start_mass"]
    )
    return {
        "controls": c,
        "stage1": stage1,
        "stage2": stage2,
        "total": stage1["delta_v"] + stage2["delta_v"],
        "twr": stage1["total_thrust"] / (stage1["start_mass"] * G0),  # thrust-to-weight
        "liftoff_mass": stage1["start_mass"],
    }


def flight_state(t, design):
    """Where is the rocket at time t of the flight? Delta-v grows while an engine burns."""
    stage2_start = STAGE1_BURN + SEPARATION_PAUSE
    end_time = stage2_start + STAGE2_BURN
    dv1 = design["stage1"]["delta_v"]
    dv2 = design["stage2"]["delta_v"]

    if t < STAGE1_BURN:
        return {"dv": dv1 * (t / STAGE1_BURN), "burning": 1, "label": "STAGE 1 BURN"}
    if t < stage2_start:
        return {"dv": dv1, "burning": 0, "label": "STAGE SEPARATION"}
    if t < end_time:
        return {
            "dv": dv1 + dv2 * ((t - stage2_start) / STAGE2_BURN),
            "burning": 2,
            "label": "STAGE 2 BURN",
        }
    return {"dv": dv1 + dv2, "burning": 0, "label": "ENGINES OFF"}


def alt_from_dv(dv):
    """How high the rocket looks on screen. The power 1.5 makes it start slowly and speed up."""
    return math.pow(clamp(dv / ORBIT_DV, 0, 1), 1.5) * 3000


def rocket_geometry(c):
    """Sizes (in pixels) of the parts of the rocket, from the player's choices."""
    return {
        "w1": 38,
        "h1": 40 + c["fuel1"] * 0.13,  # stage 1 gets taller with more fuel
        "w2": 26,
        "h2": 28 + c["fuel2"] * 0.2,
        "hc": 22 + c["payload"] * 0.4,  # nose cone size
    }


# =====================================================================
# 4. UI WIDGETS  (Pygame has no sliders or buttons, so we make our own)
# =====================================================================
class Slider:
    def __init__(self, x, y, w, label, minimum, maximum, value):
        self.x, self.y, self.w = x, y, w
        self.label = label
        self.minimum, self.maximum = minimum, maximum
        self.value = value
        self.dragging = False
        self.track = pygame.Rect(x, y + 20, w, 6)

    def set_from_mouse(self, mouse_x):
        t = clamp((mouse_x - self.track.x) / self.track.w, 0, 1)
        self.value = round(lerp(self.minimum, self.maximum, t))

    def handle_event(self, event, enabled):
        if not enabled:
            self.dragging = False
            return
        click_area = pygame.Rect(self.x - 6, self.y + 10, self.w + 12, 24)
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and click_area.collidepoint(event.pos)
        ):
            self.dragging = True
            self.set_from_mouse(event.pos[0])
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.set_from_mouse(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

    def draw(self, surface, enabled):
        label_color = TEXT_LIGHT if enabled else TEXT_DIM
        value_color = YELLOW if enabled else TEXT_DIM
        draw_text(surface, self.label, (self.x, self.y), 13, label_color)
        draw_text(
            surface,
            str(self.value),
            (self.x + self.w, self.y),
            13,
            value_color,
            "topright",
            bold=True,
        )
        pygame.draw.rect(surface, (40, 52, 90), self.track, border_radius=3)
        t = (self.value - self.minimum) / (self.maximum - self.minimum)
        filled = pygame.Rect(
            self.track.x, self.track.y, int(self.track.w * t), self.track.h
        )
        pygame.draw.rect(
            surface, BLUE if enabled else (80, 90, 120), filled, border_radius=3
        )
        knob_x = self.track.x + int(self.track.w * t)
        pygame.draw.circle(
            surface,
            WHITE if enabled else (140, 148, 170),
            (knob_x, self.track.centery),
            7,
        )


class Selector:
    """A pick-one-from-a-list box with < and > arrows."""

    def __init__(self, x, y, w, names, index):
        self.rect = pygame.Rect(x, y, w, 26)
        self.names = names
        self.index = index
        self.left = pygame.Rect(x, y, 26, 26)
        self.right = pygame.Rect(x + w - 26, y, 26, 26)

    def handle_event(self, event, enabled):
        if not enabled:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.left.collidepoint(event.pos):
                self.index = (self.index - 1) % len(self.names)
            elif self.right.collidepoint(event.pos):
                self.index = (self.index + 1) % len(self.names)

    def draw(self, surface, enabled):
        pygame.draw.rect(surface, APP_BG, self.rect, border_radius=6)
        pygame.draw.rect(surface, (51, 64, 107), self.rect, 1, border_radius=6)
        arrow_color = WHITE if enabled else (110, 118, 140)
        cy = self.rect.centery
        pygame.draw.polygon(
            surface,
            arrow_color,
            [
                (self.left.centerx + 4, cy - 6),
                (self.left.centerx + 4, cy + 6),
                (self.left.centerx - 4, cy),
            ],
        )
        pygame.draw.polygon(
            surface,
            arrow_color,
            [
                (self.right.centerx - 4, cy - 6),
                (self.right.centerx - 4, cy + 6),
                (self.right.centerx + 4, cy),
            ],
        )
        draw_text(
            surface,
            self.names[self.index],
            self.rect.center,
            13,
            WHITE if enabled else TEXT_DIM,
            "center",
        )


class Button:
    def __init__(self, rect, text, color, active_color=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color
        self.active_color = active_color or color
        self.active = False  # used for the "selected" mission button

    def clicked(self, event, enabled):
        return (
            enabled
            and event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )

    def draw(self, surface, enabled, font_size=14):
        color = self.active_color if self.active else self.color
        if not enabled and not self.active:
            color = mix_color(color, (60, 66, 90), 0.6)
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        border = GREEN if self.active else (51, 64, 107)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=8)
        draw_text(
            surface,
            self.text,
            self.rect.center,
            font_size,
            WHITE if enabled or self.active else TEXT_DIM,
            "center",
            bold=True,
        )


# =====================================================================
# 5. THE APP (game state + update + draw)
# =====================================================================
class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Delta-V: Mission Architect")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.scene = pygame.Surface((SCENE_W, SCENE_H))  # the launch picture
        self.layer = pygame.Surface(
            (SCENE_W, SCENE_H), pygame.SRCALPHA
        )  # for transparent things
        self.clock = pygame.time.Clock()
        self.running = True
        self.time_now = 0.0  # seconds since start

        self.build_panel()
        self.reset_flight_state()
        self.phase = "build"  # build -> countdown -> flight -> result
        self.target_index = 1  # the Moon
        self.design = compute_design(self.read_controls())

        # background objects, made once
        self.stars = [
            {
                "x": random.uniform(0, SCENE_W),
                "y": random.uniform(0, SCENE_H),
                "r": random.uniform(0.6, 1.8),
                "speed": random.uniform(1, 4),
                "phase": random.uniform(0, 6.28),
            }
            for _ in range(140)
        ]
        self.clouds = [
            {
                "x": random.uniform(0, SCENE_W),
                "y": random.uniform(0, SCENE_H),
                "size": random.uniform(0.7, 1.5),
                "speed": random.uniform(0.5, 0.9),
            }
            for _ in range(8)
        ]

    # ------------------------------------------------------------------
    # the control panel on the right side of the window
    # ------------------------------------------------------------------
    def build_panel(self):
        px = SCENE_W + 14  # left edge of the panel contents
        pw = SCREEN_W - px - 14  # width of the panel contents
        top = TOP_BAR + 6
        names = [e["name"] for e in ENGINES]

        # mission buttons
        bw = (pw - 12) // 3
        self.mission_buttons = []
        for i, target in enumerate(TARGETS):
            button = Button(
                (px + i * (bw + 6), top + 20, bw, 30),
                target["short"],
                (7, 11, 23),
                (10, 61, 51),
            )
            button.active = i == 1
            self.mission_buttons.append(button)

        # stage 1
        self.engine1_selector = Selector(px, top + 84, pw, names, 1)  # Raptor
        self.count1_slider = Slider(px, top + 116, pw, "Engines", 1, 12, 6)
        self.fuel1_slider = Slider(px, top + 150, pw, "Fuel (tonnes)", 20, 800, 400)

        # stage 2
        self.engine2_selector = Selector(px, top + 224, pw, names, 3)  # RL10
        self.count2_slider = Slider(px, top + 256, pw, "Engines", 1, 6, 1)
        self.fuel2_slider = Slider(px, top + 290, pw, "Fuel (tonnes)", 5, 200, 60)

        # payload
        self.payload_slider = Slider(px, top + 346, pw, "Payload (tonnes)", 1, 50, 8)

        self.sliders = [
            self.count1_slider,
            self.fuel1_slider,
            self.count2_slider,
            self.fuel2_slider,
            self.payload_slider,
        ]
        self.selectors = [self.engine1_selector, self.engine2_selector]

        self.launch_button = Button(
            (px, TOP_BAR + SCENE_H - 44, pw, 40), "LAUNCH", (230, 57, 70)
        )
        self.panel_x, self.panel_w, self.panel_top = px, pw, top

    def read_controls(self):
        return {
            "engine1": ENGINES[self.engine1_selector.index],
            "engine2": ENGINES[self.engine2_selector.index],
            "count1": self.count1_slider.value,
            "count2": self.count2_slider.value,
            "fuel1": self.fuel1_slider.value,
            "fuel2": self.fuel2_slider.value,
            "payload": self.payload_slider.value,
        }

    def controls_enabled(self):
        return self.phase == "build"

    # ------------------------------------------------------------------
    # state helpers
    # ------------------------------------------------------------------
    def reset_flight_state(self):
        self.outcome = None  # success | orbit | crash | noliftoff
        self.timer = 0.0  # seconds inside the current phase
        self.dv = 0.0  # delta-v gained so far
        self.alt_px = 0.0  # how high the rocket looks
        self.alt_speed = 0.0
        self.burning = 0  # 0 none, 1 stage 1, 2 stage 2
        self.label = ""
        self.separated = False
        self.debris = None
        self.flash_t = 0.0
        self.drift = 0.0
        self.spin = 0.0
        self.fall_v = 0.0
        self.crashed = False
        self.crash_time = 0.0
        self.smoke_acc = 0.0
        self.smoke = []
        self.sparks = []
        self.confetti = []

    def start_launch(self):
        design = compute_design(self.read_controls())
        needed = TARGETS[self.target_index]["needed"]

        # decide in advance how this flight will end
        if design["twr"] <= 1:
            outcome = "noliftoff"
        elif design["total"] >= needed:
            outcome = "success"
        elif design["total"] >= ORBIT_DV:
            outcome = "orbit"
        else:
            outcome = "crash"

        self.reset_flight_state()
        self.outcome = outcome
        self.design = design
        self.phase = "countdown"
        if outcome == "noliftoff":
            self.label = "ENGINES TOO WEAK"

    def back_to_design(self):
        self.reset_flight_state()
        self.phase = "build"

    def on_launch_clicked(self):
        if self.phase == "build":
            self.start_launch()
        elif self.phase == "result":
            self.back_to_design()

    def current_tilt(self):
        """The rocket leans over as it climbs (gravity turn) and leans toward the target after orbit."""
        climb_turn = clamp((self.alt_px - 300) / 2700, 0, 1) * 0.6
        target_turn = 0
        if self.dv > ORBIT_DV:
            target_turn = clamp((self.dv - ORBIT_DV) / 3600, 0, 1) * 0.5
        tilt = climb_turn + target_turn
        if self.outcome == "crash" and self.phase == "result":
            tilt += self.spin
        return tilt

    def flame_on(self):
        if self.phase == "countdown":
            return self.timer > COUNTDOWN_SECONDS - 1.2
        if self.phase == "flight":
            return self.burning > 0
        if self.phase == "result" and self.outcome == "noliftoff":
            return self.timer < 2.5
        return False

    def rocket_base_y(self):
        return GROUND_Y - min(self.alt_px, 220)

    def active_stage(self):
        if self.phase == "flight" and self.burning == 2:
            return 2
        return 1

    def nozzle_distance(self):
        """Distance from the rocket's base up to the nozzle of the stage that is burning."""
        if self.active_stage() == 1:
            return 0
        geo = rocket_geometry(self.design["controls"])
        return 14 + geo["h1"] + 8

    def beyond_orbit_progress(self):
        """0 while climbing to orbit, up to 1 when the destination is reached."""
        if self.dv <= ORBIT_DV:
            return 0
        needed = TARGETS[self.target_index]["needed"]
        if needed <= ORBIT_DV:
            return 0
        return clamp((self.dv - ORBIT_DV) / (needed - ORBIT_DV), 0, 1)

    # ------------------------------------------------------------------
    # events (mouse and keyboard)
    # ------------------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.on_launch_clicked()
            return

        enabled = self.controls_enabled()
        for slider in self.sliders:
            slider.handle_event(event, enabled)
        for selector in self.selectors:
            selector.handle_event(event, enabled)

        for i, button in enumerate(self.mission_buttons):
            if button.clicked(event, enabled):
                self.target_index = i
                for j, other in enumerate(self.mission_buttons):
                    other.active = j == i

        launch_enabled = self.phase in ("build", "result")
        if self.launch_button.clicked(event, launch_enabled):
            self.on_launch_clicked()

    # ------------------------------------------------------------------
    # UPDATE (runs every frame)
    # ------------------------------------------------------------------
    def update(self, dt):
        self.time_now += dt
        previous_alt = self.alt_px

        if self.phase == "build":
            self.design = compute_design(self.read_controls())
            self.dv = 0
            self.alt_px = 0
        elif self.phase == "countdown":
            self.timer += dt
            if self.timer >= COUNTDOWN_SECONDS:
                self.timer = 0
                self.phase = "result" if self.outcome == "noliftoff" else "flight"
        elif self.phase == "flight":
            self.update_flight(dt)
        elif self.phase == "result":
            self.update_result(dt)

        self.alt_speed = (self.alt_px - previous_alt) / dt if dt > 0 else 0
        if self.flash_t > 0:
            self.flash_t -= dt

        self.update_debris(dt)
        self.emit_exhaust(dt)
        self.update_particles(dt)

    def update_flight(self, dt):
        self.timer += dt
        state = flight_state(self.timer, self.design)
        self.dv = state["dv"]
        self.burning = state["burning"]
        self.label = state["label"]
        self.alt_px = alt_from_dv(self.dv)

        if not self.separated and self.timer >= STAGE1_BURN:
            self.separate_stage()

        needed = TARGETS[self.target_index]["needed"]
        if self.outcome == "success" and self.dv >= needed:
            self.finish_flight()
            return
        if self.timer >= STAGE1_BURN + SEPARATION_PAUSE + STAGE2_BURN:
            self.finish_flight()

    def separate_stage(self):
        self.separated = True
        self.flash_t = 0.35
        self.debris = {
            "x": ROCKET_X + self.drift,
            "y": self.rocket_base_y(),
            "tilt": self.current_tilt(),
            "vx": -25.0,
            "vy": 30.0,
            "spin_speed": random.uniform(-0.6, 0.6),
            "angle": 0.0,
        }

    def finish_flight(self):
        self.phase = "result"
        self.timer = 0
        self.burning = 0
        if self.outcome == "success":
            self.dv = TARGETS[self.target_index]["needed"]
            self.spawn_confetti()
        else:
            self.dv = self.design["total"]
        self.label = "ENGINES OFF"

    def update_result(self, dt):
        self.timer += dt
        if self.outcome == "crash" and not self.crashed:
            # the rocket ran out of fuel below orbit: it falls back down
            self.fall_v += 700 * dt
            self.alt_px -= self.fall_v * dt
            self.spin += 2.2 * dt
            if self.alt_px <= 0:
                self.alt_px = 0
                self.crashed = True
                self.crash_time = self.timer
                self.spawn_explosion(ROCKET_X + self.drift, GROUND_Y)
        elif self.outcome in ("orbit", "success"):
            self.drift += 14 * dt  # slowly coasting

    def update_debris(self, dt):
        if not self.debris:
            return
        d = self.debris
        d["vy"] += 260 * dt
        d["x"] += d["vx"] * dt
        d["y"] += d["vy"] * dt
        d["angle"] += d["spin_speed"] * dt
        if d["y"] > SCENE_H + 400:
            self.debris = None

    # ---------- particles: smoke, sparks, confetti ----------
    def emit_exhaust(self, dt):
        if not self.flame_on():
            return
        intensity = 0.4 if self.phase == "countdown" else 1.0
        self.smoke_acc += dt * 90 * intensity

        tilt = self.current_tilt()
        up = self.nozzle_distance()
        x = ROCKET_X + self.drift + up * math.sin(tilt)
        y = self.rocket_base_y() - up * math.cos(tilt)
        low = self.alt_px < 150

        while self.smoke_acc >= 1:
            self.smoke_acc -= 1
            if len(self.smoke) > 450:
                break
            if low:
                # on the pad the exhaust spreads sideways along the ground
                p = {
                    "x": x + random.uniform(-10, 10),
                    "y": y + random.uniform(-4, 6),
                    "vx": random.uniform(-1, 1) * random.uniform(60, 200),
                    "vy": random.uniform(-15, 25),
                    "life": 1.7,
                    "max_life": 1.7,
                    "size": random.uniform(7, 12),
                    "grow": 28,
                }
            else:
                p = {
                    "x": x + random.uniform(-4, 4),
                    "y": y + 8,
                    "vx": -math.sin(tilt) * random.uniform(60, 150)
                    + random.uniform(-20, 20),
                    "vy": math.cos(tilt) * random.uniform(60, 150),
                    "life": 1.0,
                    "max_life": 1.0,
                    "size": random.uniform(4, 7),
                    "grow": 14,
                }
            self.smoke.append(p)

    def spawn_explosion(self, x, y):
        colors = [
            (255, 209, 102),
            (255, 159, 28),
            (239, 71, 111),
            (217, 217, 217),
            (255, 243, 176),
        ]
        for i in range(90):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(40, 360)
            self.sparks.append(
                {
                    "x": x,
                    "y": y - 20,
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed - 120,
                    "life": random.uniform(0.6, 1.6),
                    "max_life": 1.6,
                    "size": random.uniform(2, 6),
                    "color": colors[i % len(colors)],
                }
            )

    def spawn_confetti(self):
        colors = [
            (255, 209, 102),
            (6, 214, 160),
            (239, 71, 111),
            (17, 138, 178),
            (255, 255, 255),
        ]
        for i in range(90):
            self.confetti.append(
                {
                    "x": random.uniform(0, SCENE_W),
                    "y": random.uniform(-300, 0),
                    "vx": random.uniform(-30, 30),
                    "vy": random.uniform(60, 160),
                    "rot": random.uniform(0, 6.28),
                    "vr": random.uniform(-5, 5),
                    "w": random.uniform(5, 9),
                    "h": random.uniform(8, 14),
                    "color": colors[i % len(colors)],
                }
            )

    def update_particles(self, dt):
        camera_shift = (
            self.alt_speed if self.alt_px > 220 else 0
        )  # the "camera" follows the rocket

        for s in self.smoke:
            s["x"] += s["vx"] * dt
            s["y"] += (s["vy"] + camera_shift) * dt
            s["size"] += s["grow"] * dt
            s["life"] -= dt
        self.smoke = [s for s in self.smoke if s["life"] > 0]

        for sp in self.sparks:
            sp["vy"] += 450 * dt
            sp["x"] += sp["vx"] * dt
            sp["y"] += sp["vy"] * dt
            sp["life"] -= dt
        self.sparks = [sp for sp in self.sparks if sp["life"] > 0]

        for c in self.confetti:
            c["x"] += c["vx"] * dt
            c["y"] += c["vy"] * dt
            c["rot"] += c["vr"] * dt
        self.confetti = [c for c in self.confetti if c["y"] <= SCENE_H + 20]

    # ------------------------------------------------------------------
    # DRAW: the scene (sky, ground, rocket...)
    # ------------------------------------------------------------------
    def clear_layer(self):
        self.layer.fill((0, 0, 0, 0))
        return self.layer

    def draw_sky(self):
        f = clamp(self.alt_px / 2400, 0, 1)  # 0 = ground level, 1 = deep space
        top = mix_color((46, 124, 214), (2, 3, 12), f)
        bottom = mix_color((188, 228, 250), (4, 6, 20), f)
        strip = 3
        for y in range(0, SCENE_H, strip):
            color = mix_color(top, bottom, y / SCENE_H)
            pygame.draw.rect(self.scene, color, (0, y, SCENE_W, strip))

    def draw_stars(self):
        visible = clamp((self.alt_px - 1200) / 1200, 0, 1)
        if visible <= 0:
            return
        for s in self.stars:
            twinkle = 0.55 + 0.45 * math.sin(self.time_now * s["speed"] + s["phase"])
            brightness = int(255 * visible * twinkle)
            color = (brightness, brightness, brightness)
            pygame.draw.circle(
                self.scene, color, (int(s["x"]), int(s["y"])), max(1, round(s["r"]))
            )

    def draw_sun(self):
        f = clamp(self.alt_px / 2000, 0, 1)
        if f >= 1:
            return
        y = 100 + self.alt_px * 0.25
        for i in range(10):  # soft glow = rings getting brighter toward the middle
            radius = 90 - i * 6
            draw_alpha_circle(
                self.scene, (255, 244, 190), (150, y), radius, 10 * (1 - f)
            )
        draw_alpha_circle(self.scene, (255, 246, 200), (150, y), 34, 255 * (1 - f))

    def draw_clouds(self):
        alpha = (1 - clamp((self.alt_px - 700) / 900, 0, 1)) * 0.9
        if alpha <= 0:
            return
        layer = self.clear_layer()
        span = SCENE_H + 200
        for c in self.clouds:
            y = ((c["y"] + self.alt_px * c["speed"]) % span) - 100
            x, s = c["x"], c["size"]
            for dx, dy, rx, ry in [(0, 0, 60, 20), (-35, 6, 38, 15), (38, 7, 40, 14)]:
                rect = pygame.Rect(0, 0, rx * 2 * s, ry * 2 * s)
                rect.center = (x + dx * s, y + dy * s)
                pygame.draw.ellipse(layer, (255, 255, 255, 255), rect)
        layer.set_alpha(int(alpha * 255))
        self.scene.blit(layer, (0, 0))
        layer.set_alpha(255)

    def draw_earth_limb(self):
        visible = clamp((self.alt_px - 1500) / 800, 0, 1)
        if visible <= 0:
            return
        q = self.beyond_orbit_progress()
        rise = clamp((self.alt_px - 1800) / 1200, 0, 1) * 80
        top_y = SCENE_H - 40 - rise + q * 260
        radius = 1500
        layer = self.clear_layer()
        center = (SCENE_W // 2, int(top_y + radius))
        pygame.draw.circle(layer, (20, 82, 160, 255), center, radius)
        pygame.draw.circle(
            layer, (140, 210, 255, 190), center, radius, 5
        )  # thin glowing atmosphere
        layer.set_alpha(int(visible * 255))
        self.scene.blit(layer, (0, 0))
        layer.set_alpha(255)

    def draw_ball(self, center, radius, light, dark):
        """A planet with simple shading: circles getting smaller and brighter toward the light."""
        steps = 22
        for i in range(steps):
            t = i / (steps - 1)
            r = radius * (1 - t * 0.85)
            offset = radius * 0.3 * t
            color = mix_color(dark, light, t)
            pygame.draw.circle(
                self.scene,
                color,
                (int(center[0] - offset), int(center[1] - offset)),
                max(1, int(r)),
            )

    def draw_destination(self):
        if self.target_index == 0:
            return
        q = self.beyond_orbit_progress()
        if q <= 0:
            return
        cx = 710
        cy = -90 + q * 230
        r = 20 + q * 80

        if self.target_index == 1:
            # THE MOON
            pygame.draw.circle(self.scene, (141, 141, 150), (int(cx), int(cy)), int(r))
            self.draw_ball((cx, cy), r, (240, 240, 240), (141, 141, 150))
            for dx, dy, size in [
                (-0.4, -0.2, 0.22),
                (0.3, 0.3, 0.18),
                (0.1, -0.5, 0.12),
                (-0.2, 0.5, 0.14),
                (0.55, -0.1, 0.1),
            ]:
                draw_alpha_circle(
                    self.scene, (90, 90, 100), (cx + dx * r, cy + dy * r), size * r, 90
                )
        else:
            # MARS
            pygame.draw.circle(self.scene, (168, 68, 31), (int(cx), int(cy)), int(r))
            self.draw_ball((cx, cy), r, (242, 160, 116), (168, 68, 31))
            layer = self.clear_layer()
            pygame.draw.ellipse(
                layer,
                (90, 30, 10, 100),
                pygame.Rect(cx - r * 0.65, cy - r * 0.08, r * 0.9, r * 0.36),
            )
            pygame.draw.ellipse(
                layer,
                (90, 30, 10, 100),
                pygame.Rect(cx + r * 0.13, cy - r * 0.37, r * 0.44, r * 0.24),
            )
            self.scene.blit(layer, (0, 0))
            pygame.draw.ellipse(
                self.scene,
                (245, 245, 245),
                pygame.Rect(cx - r * 0.28, cy - r * 1.01, r * 0.56, r * 0.18),
            )

        if q > 0.25:
            draw_text(
                self.scene,
                TARGETS[self.target_index]["short"].upper(),
                (cx, cy + r + 22),
                15,
                (207, 216, 245),
                "center",
                bold=True,
            )

    def draw_ground(self):
        shift = max(0, self.alt_px - 220)
        if shift > 330:
            return
        g = GROUND_Y + shift  # the ground line on screen
        s = self.scene

        # far hills
        hills = [(0, g), (0, g - 40)]
        hills += quad_points((0, g - 40), (160, g - 95), (320, g - 35))
        hills += quad_points((320, g - 35), (520, g - 80), (700, g - 30))
        hills += quad_points((700, g - 30), (840, g - 70), (SCENE_W, g - 38))
        hills += [(SCENE_W, g)]
        pygame.draw.polygon(s, (79, 127, 90), hills)

        # grass
        pygame.draw.rect(s, (61, 107, 63), (0, g, SCENE_W, SCENE_H + 400))

        # launch pad
        pygame.draw.rect(s, (138, 143, 156), (ROCKET_X - 75, g, 150, 10))
        pygame.draw.rect(s, (93, 98, 112), (ROCKET_X - 75, g + 10, 150, 6))

        # launch tower with cross braces
        tx = ROCKET_X - 118
        pygame.draw.rect(s, (75, 84, 104), (tx, g - 250, 18, 250))
        y = g
        while y > g - 250:
            pygame.draw.line(s, (125, 135, 159), (tx, y), (tx + 18, y - 36), 2)
            pygame.draw.line(s, (125, 135, 159), (tx + 18, y), (tx, y - 36), 2)
            y -= 36
        if int(self.time_now * 2) % 2 == 0:  # blinking red light
            pygame.draw.circle(s, (230, 57, 70), (tx + 9, int(g - 256)), 4)
        if self.phase in (
            "build",
            "countdown",
        ):  # service arms hold the rocket until liftoff
            pygame.draw.line(
                s, (154, 165, 184), (tx + 18, g - 150), (ROCKET_X - 22, g - 150), 4
            )
            pygame.draw.line(
                s, (154, 165, 184), (tx + 18, g - 220), (ROCKET_X - 16, g - 220), 4
            )

    # ---------- the rocket ----------
    def draw_flame(self, surface, cx, y, width, length):
        """A flame is three triangles on top of each other: orange, yellow, white-hot."""
        layers = [
            ((255, 140, 30), 1.0, 1.0),
            ((255, 200, 80), 0.65, 0.72),
            ((255, 246, 200), 0.32, 0.45),
        ]
        for color, width_scale, length_scale in layers:
            half = width * width_scale / 2
            pygame.draw.polygon(
                surface,
                color,
                [(cx - half, y), (cx + half, y), (cx, y + length * length_scale)],
            )

    def draw_stage1(self, surface, ox, oy, geo, controls, with_flame):
        """(ox, oy) is the point on the ground under the middle of the nozzles."""
        top = oy - (14 + geo["h1"])
        half = geo["w1"] / 2

        # fins
        fin_color = (192, 57, 43)
        pygame.draw.polygon(
            surface,
            fin_color,
            [(ox - half, oy - 48), (ox - half - 15, oy - 12), (ox - half, oy - 18)],
        )
        pygame.draw.polygon(
            surface,
            fin_color,
            [(ox + half, oy - 48), (ox + half + 15, oy - 12), (ox + half, oy - 18)],
        )

        # engine nozzles (and flames)
        n = controls["count1"]
        slot = (geo["w1"] - 8) / n
        nozzle_w = max(2, min(9, slot - 1))
        for i in range(n):
            cx = ox - half + 4 + slot * (i + 0.5)
            pygame.draw.polygon(
                surface,
                controls["engine1"]["color"],
                [
                    (cx - nozzle_w * 0.3, oy - 14),
                    (cx + nozzle_w * 0.3, oy - 14),
                    (cx + nozzle_w * 0.5, oy),
                    (cx - nozzle_w * 0.5, oy),
                ],
            )
            if with_flame:
                length = (24 + controls["engine1"]["thrust"] / 80) * random.uniform(
                    0.85, 1.15
                )
                self.draw_flame(surface, cx, oy, max(3, nozzle_w * 1.3), length)

        # body
        body = pygame.Rect(
            round(ox - half), round(top), round(geo["w1"]), round(geo["h1"])
        )
        pygame.draw.rect(surface, (241, 243, 248), body)
        pygame.draw.rect(
            surface, (43, 51, 80), (body.x, body.y + round(geo["h1"] * 0.12), body.w, 8)
        )  # dark band
        pygame.draw.rect(
            surface, (211, 216, 230), (body.right - 9, body.y, 9, body.h)
        )  # shading
        pygame.draw.rect(surface, (179, 187, 208), body, 1)

    def draw_upper(self, surface, ox, oy, geo, controls, with_flame):
        y1_top = oy - (14 + geo["h1"])
        y2_bottom = y1_top - 8
        y2_top = y2_bottom - geo["h2"]

        # stage 2 nozzles (and flames)
        n2 = min(controls["count2"], 4)
        for i in range(n2):
            cx = ox + (i - (n2 - 1) / 2) * 6
            pygame.draw.polygon(
                surface,
                controls["engine2"]["color"],
                [
                    (cx - 1.5, y2_bottom),
                    (cx + 1.5, y2_bottom),
                    (cx + 3, y2_bottom + 8),
                    (cx - 3, y2_bottom + 8),
                ],
            )
            if with_flame:
                length = (16 + controls["engine2"]["thrust"] / 18) * random.uniform(
                    0.85, 1.15
                )
                self.draw_flame(surface, cx, y2_bottom + 8, 6, length)

        # interstage: narrows from stage 1 width to stage 2 width
        pygame.draw.polygon(
            surface,
            (154, 163, 186),
            [
                (ox - geo["w1"] / 2, y1_top),
                (ox + geo["w1"] / 2, y1_top),
                (ox + geo["w2"] / 2, y2_bottom),
                (ox - geo["w2"] / 2, y2_bottom),
            ],
        )

        # stage 2 body
        body = pygame.Rect(
            round(ox - geo["w2"] / 2), round(y2_top), round(geo["w2"]), round(geo["h2"])
        )
        pygame.draw.rect(surface, (223, 228, 238), body)
        pygame.draw.rect(surface, (43, 51, 80), (body.x, body.y + 6, body.w, 5))
        pygame.draw.rect(surface, (196, 202, 219), (body.right - 7, body.y, 7, body.h))

        # nose cone with the payload (curved sides)
        w2, hc = geo["w2"], geo["hc"]
        cone = quad_points(
            (ox - w2 / 2, y2_top), (ox - w2 / 2, y2_top - hc * 0.8), (ox, y2_top - hc)
        )
        cone += quad_points(
            (ox, y2_top - hc), (ox + w2 / 2, y2_top - hc * 0.8), (ox + w2 / 2, y2_top)
        )[1:]
        pygame.draw.polygon(surface, (231, 76, 60), cone)
        pygame.draw.circle(
            surface, (143, 216, 255), (round(ox), round(y2_top - 7)), 5
        )  # window
        pygame.draw.circle(surface, (43, 51, 80), (round(ox), round(y2_top - 7)), 5, 1)

    def make_rocket_image(self, part, flame1, flame2):
        """
        Draw the rocket on its own transparent picture (so we can rotate it later).
        part: 'full' = both stages, 'upper' = stage 2 only, 'booster' = stage 1 only
        Returns (image, pivot) where pivot is the point on the image that sits on the ground.
        """
        controls = self.design["controls"]
        geo = rocket_geometry(controls)
        image = pygame.Surface((170, 440), pygame.SRCALPHA)
        pivot = (85, 350)
        if part in ("full", "booster"):
            self.draw_stage1(image, pivot[0], pivot[1], geo, controls, flame1)
        if part in ("full", "upper"):
            self.draw_upper(image, pivot[0], pivot[1], geo, controls, flame2)
        return image, pivot

    def draw_rocket_scene(self):
        if self.outcome == "crash" and self.crashed:
            return  # it exploded: hide the rocket

        shake = 0
        if self.phase == "countdown" and self.timer > COUNTDOWN_SECONDS - 1.2:
            shake = 1.2
        if self.phase == "flight" and self.alt_px < 120:
            shake = 2
        if self.phase == "result" and self.outcome == "noliftoff" and self.timer < 2.5:
            shake = 3

        flames = self.flame_on()
        if not self.separated:
            image, pivot = self.make_rocket_image("full", flames, False)
        else:
            image, pivot = self.make_rocket_image(
                "upper", False, flames and self.active_stage() == 2
            )

        position = (
            ROCKET_X + self.drift + random.uniform(-shake, shake),
            self.rocket_base_y() + random.uniform(-shake, shake) * 0.5,
        )
        blit_rotated(
            self.scene, image, position, pivot, -math.degrees(self.current_tilt())
        )

    def draw_debris(self):
        if not self.debris:
            return
        d = self.debris
        image, pivot = self.make_rocket_image("booster", False, False)
        blit_rotated(
            self.scene,
            image,
            (d["x"], d["y"]),
            pivot,
            -math.degrees(d["tilt"] + d["angle"]),
        )

    def draw_smoke(self):
        if not self.smoke:
            return
        layer = self.clear_layer()
        for s in self.smoke:
            a = clamp(s["life"] / s["max_life"], 0, 1) * 0.45
            pygame.draw.circle(
                layer,
                (235, 235, 240, int(a * 255)),
                (int(s["x"]), int(s["y"])),
                max(1, int(s["size"])),
            )
        self.scene.blit(layer, (0, 0))

    def draw_sparks_and_confetti(self):
        for sp in self.sparks:
            alpha = clamp(sp["life"] / sp["max_life"], 0, 1)
            color = mix_color((0, 0, 0), sp["color"], alpha)
            pygame.draw.circle(
                self.scene, color, (int(sp["x"]), int(sp["y"])), max(1, int(sp["size"]))
            )
        # brief white flash at the moment of impact
        if self.crashed and self.timer - self.crash_time < 0.2:
            fade = 1 - (self.timer - self.crash_time) / 0.2
            draw_alpha_rect(
                self.scene, (255, 240, 200), (0, 0, SCENE_W, SCENE_H), 200 * fade
            )

        for c in self.confetti:
            cos_r, sin_r = math.cos(c["rot"]), math.sin(c["rot"])
            corners = []
            for dx, dy in [
                (-c["w"] / 2, -c["h"] / 2),
                (c["w"] / 2, -c["h"] / 2),
                (c["w"] / 2, c["h"] / 2),
                (-c["w"] / 2, c["h"] / 2),
            ]:
                corners.append(
                    (c["x"] + dx * cos_r - dy * sin_r, c["y"] + dx * sin_r + dy * cos_r)
                )
            pygame.draw.polygon(self.scene, c["color"], corners)

    def draw_separation_flash(self):
        if self.flash_t <= 0 or not self.debris:
            return
        t = self.flash_t / 0.35
        x = ROCKET_X + self.drift
        y = self.rocket_base_y() - 60
        draw_alpha_circle(self.scene, WHITE, (x, y), 20 + (1 - t) * 50, 200 * t)

    # ---------- HUD and messages on the scene ----------
    def draw_chip(self, text, x, y, color):
        font = get_font(14, True)
        width = font.size(text)[0] + 24
        draw_alpha_rect(self.scene, (5, 8, 20), (x, y, width, 28), 180)
        pygame.draw.rect(self.scene, color, (x, y, 4, 28))
        draw_text(self.scene, text, (x + 14, y + 14), 14, WHITE, "midleft", bold=True)

    def draw_hud(self):
        target = TARGETS[self.target_index]

        if self.phase == "build":
            self.draw_chip(
                f"MISSION: {target['name']}  (needs {format_number(target['needed'])} m/s)",
                14,
                14,
                GREEN,
            )
            draw_text(
                self.scene,
                "Design your rocket on the right, then press LAUNCH",
                (SCENE_W // 2, SCENE_H - 24),
                15,
                (230, 230, 235),
                "center",
                bold=True,
            )
            return

        if self.phase == "countdown":
            remaining = math.ceil(COUNTDOWN_SECONDS - self.timer - 0.6)
            text = str(remaining) if remaining >= 1 else "LIFTOFF!"
            if self.timer < 0.6:
                text = "3"
            draw_text(
                self.scene,
                text,
                (SCENE_W // 2 + 170, 170),
                90,
                (245, 245, 245),
                "center",
                bold=True,
            )
            self.draw_chip(f"MISSION: {target['name']}", 14, 14, GREEN)
            return

        # flight and result: status chips and the progress bar
        self.draw_chip(self.label or "FLIGHT", 14, 14, YELLOW)
        if self.phase == "flight":
            self.draw_chip(f"T+ {self.timer:.1f} s", SCENE_W - 120, 14, (143, 183, 201))

        needed = target["needed"]
        bar_x, bar_y, bar_w, bar_h = 20, SCENE_H - 40, 520, 16
        draw_alpha_rect(
            self.scene, (5, 8, 20), (bar_x - 10, bar_y - 34, bar_w + 20, 62), 180
        )
        draw_text(
            self.scene,
            f"Delta-v: {format_number(self.dv)} m/s",
            (bar_x, bar_y - 12),
            15,
            WHITE,
            "midleft",
            bold=True,
        )
        draw_text(
            self.scene,
            f"Target: {target['short']} {format_number(needed)} m/s",
            (bar_x + bar_w, bar_y - 12),
            15,
            YELLOW,
            "midright",
            bold=True,
        )
        pygame.draw.rect(self.scene, (28, 38, 68), (bar_x, bar_y, bar_w, bar_h))
        fill_color = GREEN if self.dv >= needed else BLUE
        pygame.draw.rect(
            self.scene,
            fill_color,
            (bar_x, bar_y, int(bar_w * clamp(self.dv / needed, 0, 1)), bar_h),
        )
        if needed > ORBIT_DV:
            orbit_x = bar_x + int(bar_w * ORBIT_DV / needed)
            pygame.draw.rect(self.scene, WHITE, (orbit_x - 1, bar_y - 4, 2, bar_h + 8))
            draw_text(
                self.scene,
                "orbit",
                (orbit_x, bar_y + bar_h + 8),
                11,
                (159, 176, 216),
                "center",
            )

    def overlay_alpha(self):
        if self.phase != "result":
            return 0
        if self.outcome == "crash":
            start = self.crash_time + 1.2 if self.crashed else 9999
        elif self.outcome == "noliftoff":
            start = 2.6
        else:
            start = 1.8
        return clamp((self.timer - start) / 0.6, 0, 1)

    def wrap_text(self, text, font, max_width):
        words = text.split(" ")
        lines, line = [], ""
        for word in words:
            test = f"{line} {word}" if line else word
            if font.size(test)[0] > max_width and line:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        return lines

    def draw_overlay(self):
        a = self.overlay_alpha()
        if a <= 0:
            return
        target = TARGETS[self.target_index]
        design = self.design

        if self.outcome == "success":
            title, color = "MISSION SUCCESS!", GREEN
            lines = [
                f"Your rocket reached {target['name']}.",
                f"Delta-v: {format_number(design['total'])} m/s  (needed {format_number(target['needed'])})",
                "Try a harder target, or a lighter and cheaper design!",
            ]
        elif self.outcome == "orbit":
            title, color = "STUCK IN ORBIT", YELLOW
            lines = [
                f"You reached Earth orbit, but {target['name']} is too far.",
                f"Delta-v: {format_number(design['total'])} m/s  (needed {format_number(target['needed'])})",
                "Add fuel, a better engine, or reduce the payload.",
            ]
        elif self.outcome == "crash":
            title, color = "MISSION FAILED", RED
            lines = [
                "The rocket ran out of fuel before reaching orbit and fell back.",
                f"Delta-v: {format_number(design['total'])} m/s  (orbit needs {format_number(ORBIT_DV)})",
                "Add fuel, a better engine, or reduce the payload.",
            ]
        else:
            title, color = "NO LIFTOFF", RED
            lines = [
                "The engines are too weak to lift the rocket.",
                f"Thrust-to-weight is {design['twr']:.2f} (it must be above 1).",
                "Add more engines or use less fuel in stage 1.",
            ]

        # the box sits on the left so the rocket and the destination stay visible
        box_x, box_y, box_w = 24, 64, 400
        font = get_font(15)
        body = []  # list of (text, colour)
        for i, line in enumerate(lines):
            for piece in self.wrap_text(line, font, box_w - 40):
                body.append((piece, YELLOW if i == 1 else (223, 230, 250)))
        box_h = 70 + len(body) * 22 + 34

        box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box.fill((4, 7, 18, 218))
        pygame.draw.rect(box, color, (0, 0, box_w, box_h), 3)
        draw_text(box, title, (20, 46), 30, color, "midleft", bold=True)
        for j, (text, text_color) in enumerate(body):
            draw_text(box, text, (20, 78 + j * 22 + 11), 15, text_color, "midleft")
        draw_text(
            box,
            "Press REDESIGN (or SPACE) to try again",
            (20, box_h - 20),
            13,
            TEXT_DIM,
            "midleft",
        )
        box.set_alpha(int(a * 255))
        self.scene.blit(box, (box_x, box_y))

    def draw_scene(self):
        self.draw_sky()
        self.draw_stars()
        self.draw_sun()
        self.draw_earth_limb()
        self.draw_destination()
        self.draw_clouds()
        self.draw_ground()
        self.draw_debris()
        self.draw_smoke()
        self.draw_rocket_scene()
        self.draw_sparks_and_confetti()
        self.draw_separation_flash()
        self.draw_hud()
        self.draw_overlay()

    # ------------------------------------------------------------------
    # DRAW: the control panel and the whole window
    # ------------------------------------------------------------------
    def draw_panel(self):
        s = self.screen
        enabled = self.controls_enabled()
        px, pw, top = self.panel_x, self.panel_w, self.panel_top
        pygame.draw.rect(
            s, PANEL_BG, (SCENE_W + 4, TOP_BAR, SCREEN_W - SCENE_W - 4, SCENE_H)
        )

        draw_text(s, "1. MISSION", (px, top), 14, YELLOW, bold=True)
        for button in self.mission_buttons:
            button.draw(s, enabled)

        draw_text(s, "2. STAGE 1 (booster)", (px, top + 62), 14, YELLOW, bold=True)
        draw_text(s, "3. STAGE 2 (upper stage)", (px, top + 202), 14, YELLOW, bold=True)
        draw_text(s, "4. PAYLOAD", (px, top + 324), 14, YELLOW, bold=True)
        for selector in self.selectors:
            selector.draw(s, enabled)
        for slider in self.sliders:
            slider.draw(s, enabled)

        # design check
        d = self.design
        y = top + 378
        rows = [
            ("Liftoff mass", f"{d['liftoff_mass']:.1f} t", YELLOW),
            (
                "Thrust-to-weight",
                f"{d['twr']:.2f}  " + ("OK" if d["twr"] > 1 else "TOO LOW"),
                GREEN if d["twr"] > 1 else RED,
            ),
            ("Stage 1 delta-v", f"{format_number(d['stage1']['delta_v'])} m/s", YELLOW),
            ("Stage 2 delta-v", f"{format_number(d['stage2']['delta_v'])} m/s", YELLOW),
            ("Total delta-v", f"{format_number(d['total'])} m/s", YELLOW),
        ]
        reach, reach_color = "nothing yet", RED
        if d["twr"] <= 1:
            reach = "can't lift off"
        else:
            for target in TARGETS:
                if d["total"] >= target["needed"]:
                    reach, reach_color = target["short"], GREEN
        rows.append(("Can reach", reach, reach_color))
        for label, value, value_color in rows:
            draw_text(s, label, (px, y), 13, TEXT_LIGHT)
            draw_text(s, value, (px + pw, y), 13, value_color, "topright", bold=True)
            y += 17

        # launch button
        if self.phase == "build":
            self.launch_button.text = "LAUNCH"
        elif self.phase == "result":
            self.launch_button.text = "REDESIGN"
        else:
            self.launch_button.text = "FLYING..."
        self.launch_button.draw(s, self.phase in ("build", "result"), font_size=18)

    def draw(self):
        self.screen.fill(APP_BG)
        draw_text(
            self.screen,
            "DELTA-V: MISSION ARCHITECT",
            (14, TOP_BAR // 2),
            20,
            WHITE,
            "midleft",
            bold=True,
        )
        draw_text(
            self.screen,
            "Design a 2-stage rocket. Launch it. Reach orbit, the Moon or Mars.",
            (SCREEN_W - 14, TOP_BAR // 2),
            13,
            TEXT_DIM,
            "midright",
        )

        self.draw_scene()
        self.screen.blit(self.scene, (0, TOP_BAR))
        pygame.draw.rect(self.screen, PANEL_BORDER, (0, TOP_BAR, SCENE_W, SCENE_H), 2)
        self.draw_panel()

        draw_text(
            self.screen,
            "delta_v = Isp x 9.81 x ln(start_mass / end_mass)   |   Engine values are approximate public figures   |   "
            "Data: NASA Planetary Fact Sheet (NSSDCA), NASA Technical Reports Server (NTRS)",
            (14, TOP_BAR + SCENE_H + BOTTOM_BAR // 2),
            11,
            TEXT_DIM,
            "midleft",
        )

    # ------------------------------------------------------------------
    # the main loop
    # ------------------------------------------------------------------
    def run(self):
        while self.running:
            dt = min(self.clock.tick(60) / 1000, 0.05)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()


# =====================================================================
# 6. START
# =====================================================================
def main():
    App().run()


if __name__ == "__main__":
    main()
