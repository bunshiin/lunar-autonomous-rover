from ursina import *
import random, math, heapq, time as _time

app = Ursina()
window.title           = "Türkiye Ay Rover — Otonom Navigasyon (TUA Gelişmiş HUD)"
window.borderless      = False
window.fullscreen      = False
window.exit_button.visible = False
window.fps_counter.enabled = True
window.color               = color.black
camera.fov                 = 85

def C_RGB(r, g, b):
    return color.rgb(r/255, g/255, b/255)
def C_RGBA(r, g, b, a):
    return color.rgba(r/255, g/255, b/255, a/255)

AmbientLight(color=C_RGB(90, 95, 110))
DirectionalLight(y=8, x=3, z=4, rotation=(30, -55, 0), color=C_RGB(255, 248, 220))

def fade(t): return t * t * t * (t * (t * 6 - 15) + 10)
def lerp_f(a, b, t): return a + t * (b - a)
def grad(h, x, y):
    h &= 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if h in (12, 14) else 0)
    return (u if not (h & 1) else -u) + (v if not (h & 2) else -v)

_perm = list(range(256))
random.shuffle(_perm)
_perm = _perm * 2

def perlin(x, y):
    xi, yi = int(math.floor(x)) & 255, int(math.floor(y)) & 255
    xf, yf = x - math.floor(x), y - math.floor(y)
    u, v   = fade(xf), fade(yf)
    aa = _perm[_perm[xi]     + yi]
    ab = _perm[_perm[xi]     + yi + 1]
    ba = _perm[_perm[xi + 1] + yi]
    bb = _perm[_perm[xi + 1] + yi + 1]
    return lerp_f(
        lerp_f(grad(aa, xf,     yf),     grad(ba, xf - 1, yf),     u),
        lerp_f(grad(ab, xf,     yf - 1), grad(bb, xf - 1, yf - 1), u), v)

def octave_noise(x, y, octaves=3, persistence=0.45, lacunarity=1.8):
    val, amp, freq, mx = 0, 1, 1, 0
    for _ in range(octaves):
        val += perlin(x * freq, y * freq) * amp
        mx  += amp
        amp *= persistence
        freq *= lacunarity
    return val / mx

CUSTOM_MAP_SIZE     = 200
WORLD_SIZE          = CUSTOM_MAP_SIZE / 2
GRID_N              = 100
CELL_SIZE           = CUSTOM_MAP_SIZE / GRID_N
TERRAIN_SUBDIV      = 100
TERRAIN_H_SCALE     = 2.0
TERRAIN_NOISE_SCALE = 0.025

def generate_features_data(count=20, area=85, min_dist=18):
    features_data = []
    attempts = 0
    while len(features_data) < count and attempts < 300:
        attempts += 1
        cx = random.uniform(-area, area)
        cz = random.uniform(-area, area)
        if math.sqrt(cx**2 + cz**2) < 15: continue
        r = random.uniform(6, 14)
        too_close = False
        for ox, oz, orad, _ in features_data:
            if math.sqrt((cx-ox)**2 + (cz-oz)**2) < (r + orad + min_dist):
                too_close = True
                break
        if not too_close:
            f_type = random.choice(['crater', 'crater', 'hill'])
            features_data.append((cx, cz, r, f_type))
    return features_data

features_list = generate_features_data(count=25, area=85, min_dist=16)

ICE_CRATER_COUNT = random.randint(3, 4)
ice_crater_indices = set(
    random.sample(
        [i for i, (_, _, _, ft) in enumerate(features_list) if ft == 'crater'],
        min(ICE_CRATER_COUNT,
            len([f for f in features_list if f[3] == 'crater']))
    )
)

ice_crater_entities = {}
mined_craters = set()  

def get_feature_modifier(wx, wz):
    mod_h = 0
    for cx, cz, r, f_type in features_list:
        d = math.sqrt((wx - cx)**2 + (wz - cz)**2)
        if d < r * 1.5:
            d_norm = d / r
            if f_type == 'crater':
                if d_norm <= 0.8:
                    mod_h -= (r * 0.25) * (1 - (d_norm / 0.8)**2)
                elif d_norm <= 1.5:
                    t = (d_norm - 0.8) / 0.7
                    mod_h += (r * 0.15) * math.sin(t * math.pi)
            elif f_type == 'hill':
                if d_norm <= 1.5:
                    t = d_norm / 1.5
                    mod_h += (r * 0.8) * (math.cos(t * math.pi / 2) ** 2)
    return mod_h

print("Ay yuzeyi yukseklik haritasi hesaplaniyor...")
_height_map = {}
def get_height(wx, wz):
    key = (round(wx, 1), round(wz, 1))
    if key not in _height_map:
        nx = wx * TERRAIN_NOISE_SCALE
        nz = wz * TERRAIN_NOISE_SCALE
        base_h = octave_noise(nx, nz) * TERRAIN_H_SCALE
        _height_map[key] = base_h + get_feature_modifier(wx, wz)
    return _height_map[key]

def build_terrain_mesh():
    print("3D terrain mesh olusturuluyor...")
    n    = TERRAIN_SUBDIV
    size = CUSTOM_MAP_SIZE
    step = size / n
    h_vals = []
    
    for iz in range(n + 1):
        row = []
        for ix in range(n + 1):
            wx = -size / 2 + ix * step
            wz = -size / 2 + iz * step
            row.append(get_height(wx, wz))
        h_vals.append(row)
        
    h_min   = min(min(r) for r in h_vals)
    h_max   = max(max(r) for r in h_vals)
    h_range = h_max - h_min if h_max != h_min else 1

    # DÜZELTME 1: Fonksiyon içeriği doğru şekilde sağa hizalandı (Indentation)
    def height_to_color(wx, wz, h):
        # 🌑 1. Albedo (yükseklikten bağımsız renk)
        albedo = octave_noise(wx * 0.01, wz * 0.01, octaves=4)
        base = 0.35 + albedo * 0.25   # gri ton

        # 🪨 2. Mikro detay (küçük krater hissi)
        micro = octave_noise(wx * 0.2, wz * 0.2, octaves=2) * 0.08
        base += micro

        # 🕳️ 3. Krater etkisi (koyu iç, parlak kenar)
        for cx, cz, r, f_type in features_list:
            if f_type != 'crater':
                continue

            d = math.sqrt((wx - cx)**2 + (wz - cz)**2)
            d_norm = d / r

            if d_norm < 1.0:
                base -= 0.25 * (1 - d_norm)   # içi koyu
            elif d_norm < 1.3:
                base += 0.15 * (1 - (d_norm - 1)/0.3)  # kenar parlak

        # 🌘 4. Fake shadow (ambient occlusion)
        neighbors = []
        for dx, dz in [(-1,0),(1,0),(0,-1),(0,1)]:
            nh = get_height(wx + dx, wz + dz)
            neighbors.append(nh)

        occlusion = sum(1 for n in neighbors if n > h) / len(neighbors)
        base *= (1 - occlusion * 0.3)

        # 🎲 5. Grain (toz efekti)
        grain = random.uniform(-0.02, 0.02)
        base += grain

        base = max(0.1, min(0.9, base))

        return color.rgb(base, base, base)

    verts, cols, tris = [], [], []
    for iz in range(n + 1):
        for ix in range(n + 1):
            wx = -size / 2 + ix * step
            wz = -size / 2 + iz * step
            h  = h_vals[iz][ix]
            verts.append((wx, h, wz))
            # DÜZELTME 2: Fonksiyona eksik olan wx ve wz argümanları eklendi
            cols.append(height_to_color(wx, wz, h))
            
    for iz in range(n):
        for ix in range(n):
            i0 = iz * (n + 1) + ix
            i1 = i0 + 1
            i2 = (iz + 1) * (n + 1) + ix
            i3 = i2 + 1
            tris += [i0, i1, i2,  i2, i1, i3]
            
    mesh = Mesh(vertices=verts, triangles=tris, colors=cols, mode='triangle')
    return Entity(model=mesh, position=(0, 0, 0), double_sided=True)

def create_ice_crystals():
    for idx in ice_crater_indices:
        cx, cz, r, _ = features_list[idx]
        crystals = []

        count = random.randint(10, 18)
        for _ in range(count):
            angle  = random.uniform(0, math.pi * 2)
            dist   = random.uniform(0, r * 0.80)
            px     = cx + math.cos(angle) * dist
            pz     = cz + math.sin(angle) * dist
            local_y = get_height(px, pz)
            py      = local_y + 0.15
            size    = random.uniform(0.18, 0.60)
            r_ch    = random.randint(160, 210)
            g_ch    = random.randint(210, 240)
            b_ch    = 255
            ent = Entity(
                model="cube",
                scale=(size, size * random.uniform(0.5, 1.2), size),
                position=(px, py, pz),
                color=C_RGB(r_ch, g_ch, b_ch),
                rotation=(random.uniform(0, 360), random.uniform(0, 360), random.uniform(0, 360)),
                unlit=True,
            )
            crystals.append(ent)

        floor_y = get_height(cx, cz) + 0.18
        floor_ent = Entity(
            model="quad",
            scale=(r * 1.8, r * 1.8),
            position=(cx, floor_y, cz),
            rotation=(90, random.uniform(0, 360), 0),
            color=C_RGBA(140, 210, 255, 120),
            double_sided=True,
            unlit=True,
        )
        ice_crater_entities[idx] = {'floor': floor_ent, 'crystals': crystals}

def mark_ice_crater_done(idx):
    if idx not in ice_crater_entities: return
    mined_craters.add(idx)
    data = ice_crater_entities[idx]
    data['floor'].color = C_RGBA(60, 200, 80, 130)
    for c in data['crystals']:
        c.color = C_RGB(60, 200, 80)

def scatter_rocks(count=120, area=88):
    rocks_data = []
    for _ in range(count):
        rx = random.uniform(-area, area)
        rz = random.uniform(-area, area)
        s  = random.uniform(0.25, 1.4)
        ry = get_height(rx, rz)
        col_val = random.randint(100, 160)
        Entity(model="sphere", scale=(s, s * random.uniform(0.5, 1.0), s),
               position=(rx, ry + s * 0.3, rz), color=C_RGB(col_val, col_val, col_val + 5))
        rocks_data.append((rx, rz, s))
    return rocks_data

def create_starfield(count=1500, radius=320):
    for _ in range(count):
        theta = random.uniform(0, math.pi)
        phi   = random.uniform(0, 2 * math.pi)
        r     = radius * random.uniform(0.85, 1.0)
        sz    = random.choice([0.3, 0.5, 0.7, 1.2])
        c_type = random.choice([(255,255,255),(180,200,255),(255,240,180),(255,180,180)])
        br    = random.uniform(0.6, 1.0)
        c = C_RGB(int(c_type[0]*br), int(c_type[1]*br), int(c_type[2]*br))
        Entity(model="sphere", scale=sz,
               position=(r*math.sin(theta)*math.cos(phi),
                         r*math.sin(theta)*math.sin(phi),
                         r*math.cos(theta)), color=c, unlit=True)

def create_earth():
    p = (120, 80, -280)
    Entity(model="sphere", scale=55,   position=p, color=C_RGB(20,60,160),      texture="noise", unlit=True)
    Entity(model="sphere", scale=55.5, position=p, color=C_RGBA(40,150,70,120),   texture="noise", unlit=True)
    Entity(model="sphere", scale=56.5, position=p, color=C_RGBA(255,255,255,100), texture="noise", unlit=True)

def surface_y(wx, wz):
    nx = wx * TERRAIN_NOISE_SCALE
    nz = wz * TERRAIN_NOISE_SCALE
    base_h = octave_noise(nx, nz) * TERRAIN_H_SCALE
    return base_h + get_feature_modifier(wx, wz)

_cost_map = None

def world_to_grid(x, z):
    gi = int((x + WORLD_SIZE) / CELL_SIZE)
    gj = int((z + WORLD_SIZE) / CELL_SIZE)
    return max(0, min(GRID_N-1, gi)), max(0, min(GRID_N-1, gj))

def grid_to_world(gi, gj):
    x = -WORLD_SIZE + (gi * CELL_SIZE) + (CELL_SIZE / 2)
    z = -WORLD_SIZE + (gj * CELL_SIZE) + (CELL_SIZE / 2)
    return x, z

def _compute_height_stats():
    sample_heights = []
    step = 4
    for i in range(0, GRID_N, step):
        for j in range(0, GRID_N, step):
            wx, wz = grid_to_world(i, j)
            sample_heights.append(get_height(wx, wz))
    return min(sample_heights), max(sample_heights)

def _is_in_ice_crater(wx, wz):
    for idx in ice_crater_indices:
        cx, cz, r, _ = features_list[idx]
        if math.sqrt((wx - cx)**2 + (wz - cz)**2) < r * 0.90:
            return True
    return False

def build_cost_map(features, rocks):
    global _cost_map
    print("Maliyet haritasi hesaplaniyor (dinamik esikler)...")
    h_min, h_max = _compute_height_stats()
    h_range = h_max - h_min if h_max != h_min else 1.0
    DEEP_THRESHOLD  = h_min + h_range * 0.18
    SLOPE_THRESHOLD = h_min + h_range * 0.38
    HIGH_THRESHOLD  = h_max - h_range * 0.15
    INF = 1e9
    _cost_map = [[0.0] * GRID_N for _ in range(GRID_N)]
    for i in range(GRID_N):
        for j in range(GRID_N):
            wx, wz = grid_to_world(i, j)
            h = get_height(wx, wz)
            if _is_in_ice_crater(wx, wz):
                _cost_map[i][j] = 2.0
                continue
                
            # YENİ: Engellere güvenlik bariyeri. (Teğet geçmek yerine etrafından dolaşmayı zorlar)
            too_close = False
            for f_idx, (cx, cz, r, f_type) in enumerate(features_list):
                if f_idx in ice_crater_indices:
                    continue 
                dist = math.sqrt((wx - cx)**2 + (wz - cz)**2)
                # Normal krater ve tepelere r * 1.5 güvenlik mesafesi eklendi
                if dist < r * 1.5:
                    too_close = True
                    break
            if too_close:
                _cost_map[i][j] = INF
                continue

            if h < DEEP_THRESHOLD or h > HIGH_THRESHOLD:
                _cost_map[i][j] = INF
                continue
            if h < SLOPE_THRESHOLD:
                ratio = (h - DEEP_THRESHOLD) / (SLOPE_THRESHOLD - DEEP_THRESHOLD + 1e-9)
                _cost_map[i][j] = 1.0 + 25.0 * (1.0 - ratio)
                continue
            neighbors_h = []
            for di, dj in ((-1,0),(1,0),(0,-1),(0,1)):
                ni, nj = i+di, j+dj
                if 0 <= ni < GRID_N and 0 <= nj < GRID_N:
                    nwx, nwz = grid_to_world(ni, nj)
                    neighbors_h.append(get_height(nwx, nwz))
            max_diff = max(abs(h - nh) for nh in neighbors_h) if neighbors_h else 0.0
            _cost_map[i][j] = 1.0 + min(8.0, max_diff * 16.0)
    for rx, rz, s in rocks:
        rgx, rgz = world_to_grid(rx, rz)
        if 0 <= rgx < GRID_N and 0 <= rgz < GRID_N:
            _cost_map[rgx][rgz] = INF
            if s > 0.8:
                for di in range(-2, 3): 
                    for dj in range(-2, 3):
                        ni, nj = rgx+di, rgz+dj
                        if 0 <= ni < GRID_N and 0 <= nj < GRID_N:
                            _cost_map[ni][nj] = INF

def astar(start_gx, start_gz, end_gx, end_gz):
    if _cost_map is None: return []
    INF_THRESH = 5e8
    D  = 1.0
    D2 = math.sqrt(2)
    def heuristic(ax, az, bx, bz):
        ddx = abs(ax - bx); ddz = abs(az - bz)
        return D * (ddx + ddz) + (D2 - 2*D) * min(ddx, ddz)
    open_heap = []
    heapq.heappush(open_heap, (0.0, start_gx, start_gz))
    came_from = {}
    g_score   = {(start_gx, start_gz): 0.0}
    while open_heap:
        _, cx, cz = heapq.heappop(open_heap)
        if cx == end_gx and cz == end_gz:
            path = []
            node = (cx, cz)
            while node in came_from:
                wx, wz = grid_to_world(*node)
                path.append(Vec3(wx, surface_y(wx, wz), wz))
                node = came_from[node]
            path.reverse()
            return path
        for dx, dz in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
            nx2, nz2 = cx + dx, cz + dz
            if not (0 <= nx2 < GRID_N and 0 <= nz2 < GRID_N): continue
            cost = _cost_map[nx2][nz2]
            if cost >= INF_THRESH: continue
            move_dist = D2 if (dx != 0 and dz != 0) else D
            tentative = g_score[(cx, cz)] + cost * move_dist
            key = (nx2, nz2)
            if tentative < g_score.get(key, 1e18):
                g_score[key]   = tentative
                came_from[key] = (cx, cz)
                h = heuristic(nx2, nz2, end_gx, end_gz)
                heapq.heappush(open_heap, (tentative + h, nx2, nz2))
    return []

MAP_SCALE  = 0.45
MAP_OFFSET = Vec2(0.65, -0.22)

class MiniMap:
    def __init__(self, features, rocks):
        self.map_bg = Entity(parent=camera.ui, model="quad",
                             scale=(MAP_SCALE, MAP_SCALE),
                             position=(MAP_OFFSET.x, MAP_OFFSET.y),
                             color=C_RGB(75, 75, 80), z=-1)
        self.border = Entity(parent=camera.ui, model="quad",
                             scale=(MAP_SCALE+0.015, MAP_SCALE+0.015),
                             position=(MAP_OFFSET.x, MAP_OFFSET.y),
                             color=C_RGB(30, 30, 35), z=-2)
        self._ice_map_dots = {}
        self._draw_obstacles(features, rocks)
        try:
            rover_tex = load_texture("rover_logo.png")
        except:
            rover_tex = None
        self.rover_dot = Entity(parent=camera.ui, model="quad",
                                texture=rover_tex, scale=(0.045, 0.045),
                                color=color.white if rover_tex else color.cyan, z=-4.8)
        self.target_dot = Entity(parent=camera.ui, z=-5, enabled=False)
        Entity(parent=self.target_dot, model="quad", scale=(0.025, 0.005), color=color.red, rotation_z=45)
        Entity(parent=self.target_dot, model="quad", scale=(0.025, 0.005), color=color.red, rotation_z=-45)
        self.path_dots = []
        Text("[ AY HARITASI ]", parent=camera.ui,
             position=(MAP_OFFSET.x - 0.1, MAP_OFFSET.y + MAP_SCALE/2 + 0.02),
             scale=0.9, color=C_RGB(200, 210, 255))
        self.target_wp = None

    def _draw_obstacles(self, features, rocks):
        for i, (cx, cz, r, f_type) in enumerate(features):
            mx, my = self._to_map(cx, cz)
            ms = (r / WORLD_SIZE) * MAP_SCALE
            if f_type == 'hill':
                feat_color = C_RGBA(180, 180, 190, 150)
            elif i in ice_crater_indices:
                feat_color = C_RGBA(100, 200, 255, 200)
            else:
                feat_color = C_RGBA(35, 35, 40, 220)
            dot = Entity(parent=camera.ui, model="sphere", scale=(ms, ms),
                         position=(mx, my), color=feat_color, z=-2.5)
            if i in ice_crater_indices:
                self._ice_map_dots[i] = dot
        for rx, rz, s in rocks:
            mx, my = self._to_map(rx, rz)
            ms = (s / WORLD_SIZE) * MAP_SCALE * 3
            Entity(parent=camera.ui, model="sphere", scale=(ms, ms),
                   position=(mx, my), color=C_RGBA(40,40,45,230), z=-3)

    def mark_ice_done(self, idx):
        if idx in self._ice_map_dots:
            self._ice_map_dots[idx].color = C_RGBA(60, 200, 80, 220)

    def _to_map(self, wx, wz):
        return MAP_OFFSET.x + (wx / WORLD_SIZE) * (MAP_SCALE / 2), \
               MAP_OFFSET.y + (wz / WORLD_SIZE) * (MAP_SCALE / 2)

    def _from_map_click(self, sx, sy):
        return ((sx - MAP_OFFSET.x) / (MAP_SCALE / 2)) * WORLD_SIZE, \
               ((sy - MAP_OFFSET.y) / (MAP_SCALE / 2)) * WORLD_SIZE

    def is_on_map(self, sx, sy):
        half = MAP_SCALE / 2
        return abs(sx - MAP_OFFSET.x) < half and abs(sy - MAP_OFFSET.y) < half

    def handle_click(self, sx, sy):
        if not self.is_on_map(sx, sy): return False
        wx, wz = self._from_map_click(sx, sy)
        wx = max(-WORLD_SIZE+2, min(WORLD_SIZE-2, wx))
        wz = max(-WORLD_SIZE+2, min(WORLD_SIZE-2, wz))
        self.target_wp = (wx, wz)
        mx, my = self._to_map(wx, wz)
        self.target_dot.position = (mx, my)
        self.target_dot.enabled  = True
        self.clear_path()
        nav_status.text  = "SPACE ile rotayi baslatin"
        nav_status.color = C_RGB(80, 220, 120)
        return True

    def show_path(self, path_world):
        self.clear_path()
        for pt in path_world[::3]:
            mx, my = self._to_map(pt.x, pt.z)
            d = Entity(parent=camera.ui, model="quad", scale=(0.008, 0.008),
                       position=(mx, my), color=color.yellow, z=-4)
            self.path_dots.append(d)

    def clear_path(self):
        for d in self.path_dots: destroy(d)
        self.path_dots = []

    def reset(self):
        self.target_wp = None
        self.target_dot.enabled = False
        self.clear_path()
        nav_status.text  = "Haritadan hedef secin (kirmizi carpi)"
        nav_status.color = C_RGB(255, 100, 100)

    def update_rover(self, rx, rz, ry_deg):
        mx, my = self._to_map(rx, rz)
        self.rover_dot.position   = (mx, my)
        self.rover_dot.rotation_z = -ry_deg

ROVER_GROUND_OFFSET = 0.65

# ─── Görev Sonu Temizliği (Yardımcı Fonksiyon) ───────────────────────────────
def check_and_clear_mission():
    """Tum kraterler toplandiysa, ekrandaki yesil marker ve sari noktalari temizler."""
    if len(mined_craters) >= len(ice_crater_indices):
        nav_status.text  = "GOREV BASARILI! Tum buzlar toplandi."
        nav_status.color = C_RGB(60, 200, 80)
        
        autonomy.stop()
        minimap.clear_path()
        minimap.target_dot.enabled = False
        
        # Minimap'teki yeşil marker'ları yok eder
        for dot in minimap._ice_map_dots.values():
            destroy(dot)
        minimap._ice_map_dots.clear()
        return True
    return False

# ─── Buz turu yoneticisi (H tusu) ────────────────────────────────────────────
class IceTourController:
    DIG_WAIT   = 7.5    
    ICE_RADIUS = 12.0   

    def __init__(self):
        self.active      = False
        self.current_idx = None
        self._wait_timer = 0.0
        self._digging    = False

    def start(self, rover_x, rover_z):
        if check_and_clear_mission():
            return
        
        self.active      = True
        self._digging    = False
        self._wait_timer = 0.0
        self.current_idx = None
        self._go_next()

    def _go_next(self):
        remaining = [i for i in ice_crater_indices if i not in mined_craters]
        if not remaining:
            self.active = False
            check_and_clear_mission() # Tur bittiğinde temizliği tetikler
            return

        def dist_to(idx):
            cx, cz, _, _ = features_list[idx]
            return math.sqrt((rover.x - cx)**2 + (rover.z - cz)**2)

        self.current_idx = min(remaining, key=dist_to)
        cx, cz, _, _ = features_list[self.current_idx]
        self._navigate_to(cx, cz)

    def _navigate_to(self, cx, cz):
        sg, si = world_to_grid(rover.x, rover.z)
        eg, ei = world_to_grid(cx, cz)
        path   = astar(sg, si, eg, ei)
        if path:
            minimap.show_path(path)
            autonomy.start(path, (cx, cz))
            remaining_count = len([i for i in ice_crater_indices if i not in mined_craters])
            nav_status.text  = f"Buz turu: {remaining_count} krater kaldi — hedefe gidiliyor..."
            nav_status.color = C_RGB(100, 210, 255)
        else:
            nav_status.text  = "Rota bulunamadi, sonraki kratere geciliyor..."
            nav_status.color = color.orange
            mined_craters.add(self.current_idx)
            self._go_next()

    def update(self, dt):
        if not self.active: return

        if self._digging:
            self._wait_timer -= dt
            kalan_s = max(0.0, self._wait_timer)
            remaining_count = len([i for i in ice_crater_indices if i not in mined_craters])
            nav_status.text  = f"Kaziliyor... ({kalan_s:.1f}s) | {remaining_count} krater kaldi"
            nav_status.color = C_RGB(100, 210, 255)
            if self._wait_timer <= 0:
                self._digging = False
                mark_ice_crater_done(self.current_idx)
                if self.current_idx in minimap._ice_map_dots:
                    minimap.mark_ice_done(self.current_idx)
                _set_dig_warning(False)
                self._go_next()
            return

        if self.current_idx is not None and not autonomy.active:
            cx, cz, r, _ = features_list[self.current_idx]
            d = math.sqrt((rover.x - cx)**2 + (rover.z - cz)**2)
            if d < self.ICE_RADIUS:
                autonomy.stop()
                rover.arm.dig()
                _set_dig_warning(True)
                self._digging    = True
                self._wait_timer = self.DIG_WAIT
                nav_status.text  = f"Kaziliyor... ({self.DIG_WAIT:.1f}s)"
                nav_status.color = C_RGB(100, 210, 255)

    def stop(self):
        self.active      = False
        self._digging    = False
        self._wait_timer = 0.0
        _set_dig_warning(False)

# ─────────────────────────────────────────────────────────────────────────────

class AutonomyController:
    LOOKAHEAD   = 5.0
    GOAL_THRESH = 4.0
    MAX_SPEED   = 8.0
    TURN_RATE   = 100.0

    def __init__(self):
        self.active       = False
        self.path         = []
        self.wp_idx       = 0
        self.goal         = None
        self._markers     = []
        self.total_puan   = 0.0
        self.adim_sayisi  = 0
        self._visited_ice = set()

    def start(self, path, goal):
        self.clear_markers()
        self.path         = path
        self.wp_idx       = 0
        self.goal         = goal
        self.active       = True
        self.total_puan   = 0.0
        self.adim_sayisi  = 0
        self._visited_ice = set()
        for pt in path[::4]:
            m = Entity(model="sphere", scale=0.45, position=(pt.x, pt.y + 0.5, pt.z),
                       color=color.yellow, unlit=True)
            self._markers.append(m)

    def stop(self):
        self.active = False
        self.clear_markers()

    def clear_markers(self):
        for m in self._markers: destroy(m)
        self._markers = []

    def update(self, rover_ent, dt):
        if not self.active or not self.path: return
        rx, rz = rover_ent.x, rover_ent.z
        h = get_height(rx, rz)
        
        if _is_in_ice_crater(rx, rz):
            puan = 1.0 
        else:
            if h < -0.8 or h > 3.0: puan = 0.5
            elif h < 0.0: puan = 0.8
            else: puan = 1.0
            
        self.total_puan  += puan
        self.adim_sayisi += 1
        guvenlik_orani   = max(0.0, min(1.0, self.total_puan / self.adim_sayisi))
        guvenlik_yuzdesi = guvenlik_orani * 100
        
        if guvenlik_yuzdesi < 65 and self.adim_sayisi > 50:
            self.stop()
            nav_status.text  = f"KRITIK HATA! GUVENLIK %{guvenlik_yuzdesi:.1f} - GOREV IPTAL"
            nav_status.color = color.red
            minimap.reset()
            return

        if not ice_tour.active:
            for idx in ice_crater_indices:
                if idx in mined_craters or idx in self._visited_ice: continue 
                
                cx, cz, r, _ = features_list[idx]
                dist_to_ice = math.sqrt((rx - cx)**2 + (rz - cz)**2)
                if dist_to_ice < r * 0.75:
                    self._visited_ice.add(idx)
                    rover_ent.arm.dig()
                    _set_dig_warning(True)
                    invoke(_set_dig_warning, False, delay=7.5)
                    
                    def manual_dig_complete():
                        mark_ice_crater_done(idx)
                        if idx in minimap._ice_map_dots:
                            minimap.mark_ice_done(idx)
                        check_and_clear_mission() # Kazı sonrası oyun bittiyse temizliği tetikler
                    
                    invoke(manual_dig_complete, delay=7.5)
                    nav_status.text  = "Buz krateri! Otomatik kazma basladi..."
                    nav_status.color = C_RGB(100, 210, 255)
                    break

        if self.goal:
            gx, gz = self.goal
            if math.sqrt((rx - gx)**2 + (rz - gz)**2) < self.GOAL_THRESH:
                self.stop()
                if not ice_tour.active:
                    nav_status.text  = "Hedefe ulasildi!"
                    nav_status.color = C_RGB(80, 255, 120)
                    minimap.reset()
                return
        target = None
        for i in range(self.wp_idx, len(self.path)):
            pt   = self.path[i]
            dist = math.sqrt((pt.x - rx)**2 + (pt.z - rz)**2)
            if dist >= self.LOOKAHEAD:
                target      = pt
                self.wp_idx = max(self.wp_idx, i)
                break
        if target is None and self.path: target = self.path[-1]
        for i, m in enumerate(self._markers):
            dist_to_wp = math.sqrt((m.x - rx)**2 + (m.z - rz)**2)
            if i * 4 < self.wp_idx:
                m.color = color.gray; m.scale = 0.25
            elif dist_to_wp < 12:
                r_val = 1.0 - guvenlik_orani
                g_val = guvenlik_orani
                m.color = color.rgb(r_val, g_val, 0.0); m.scale = 0.6
            else:
                m.color = color.yellow
        if target is None: return
        dx = target.x - rx
        dz = target.z - rz
        target_angle = math.degrees(math.atan2(dx, dz))
        diff = target_angle - rover_ent.rotation_y
        while diff >  180: diff -= 360
        while diff < -180: diff += 360
        max_turn = self.TURN_RATE * dt
        rover_ent.rotation_y += max(-max_turn, min(max_turn, diff))
        speed_factor = max(0.1, 1.0 - abs(diff) / 120.0)
        spd = self.MAX_SPEED * speed_factor
        rover_ent.x += math.sin(math.radians(rover_ent.rotation_y)) * spd * dt
        rover_ent.z += math.cos(math.radians(rover_ent.rotation_y)) * spd * dt
        wb_z = 2.4; wb_x = 1.5
        hf = surface_y(rover_ent.x + math.sin(math.radians(rover_ent.rotation_y))*wb_z,
                       rover_ent.z + math.cos(math.radians(rover_ent.rotation_y))*wb_z)
        hb = surface_y(rover_ent.x - math.sin(math.radians(rover_ent.rotation_y))*wb_z,
                       rover_ent.z - math.cos(math.radians(rover_ent.rotation_y))*wb_z)
        hr = surface_y(rover_ent.x + math.cos(math.radians(rover_ent.rotation_y))*wb_x,
                       rover_ent.z - math.sin(math.radians(rover_ent.rotation_y))*wb_x)
        hl = surface_y(rover_ent.x - math.cos(math.radians(rover_ent.rotation_y))*wb_x,
                       rover_ent.z + math.sin(math.radians(rover_ent.rotation_y))*wb_x)
        avg_ground_h = (hf + hb + hr + hl) / 4.0
        rover_ent.y = avg_ground_h + ROVER_GROUND_OFFSET
        target_pitch = math.degrees(math.atan2(hf - hb, wb_z * 2))
        target_roll  = math.degrees(math.atan2(hr - hl, wb_x * 2))
        rover_ent.rotation_x = lerp(rover_ent.rotation_x, -target_pitch, dt * 5)
        rover_ent.rotation_z = lerp(rover_ent.rotation_z, target_roll,   dt * 5)
        # ... (Burası eski kodda target_roll ve rotation_x/z lerp hesaplamalarının hemen altı) ...
        rover_ent.rotation_x = lerp(rover_ent.rotation_x, -target_pitch, dt * 5)
        rover_ent.rotation_z = lerp(rover_ent.rotation_z, target_roll,   dt * 5)
        
        # YENİ: Gerçekçi Diferansiyel Tekerlek Dönüşü (Skid-Steering)
        # Manevra sırasında dönüş açısına (diff) göre tekerleklere ters devir verilir.
        turn_spin = (diff / 5.0) * 100 * dt  # Dönüş ivmesi
        forward_spin = spd * 80 * dt         # İleri/Geri ivmesi
        
        for w in rover_ent.wheels:
            if w.x < 0: # Sol tekerlekler
                w.rotation_x += (forward_spin + turn_spin)
            else:       # Sağ tekerlekler
                w.rotation_x += (forward_spin - turn_spin)

# ═══════════════════════════════════════════════════════════════════════════════
# ROBOTiK KOL
# ═══════════════════════════════════════════════════════════════════════════════
class RoboticArm:
    def __init__(self, parent_entity):
        self.POSE_IDLE  = ( -20,  -110,  30)
        self.POSE_LOWER = (  45,   -40, -10)
        self.POSE_DIG   = (  55,   -20,  80)
        self.POSE_LIFT  = (  10,   -90,  40)
        self.POSE_STORE = ( -40,  -130,  50)
        self.is_busy = False

        self.mount = Entity(parent=parent_entity, position=(1.6, 0.9, 2.0))
        Entity(parent=self.mount, model="cube", scale=(0.4, 0.6, 0.4), color=C_RGB(80, 80, 85))

        self.shoulder = Entity(parent=self.mount, position=(0, 0.2, 0), rotation_x=self.POSE_IDLE[0])
        Entity(parent=self.shoulder, model=Cylinder(resolution=16), scale=(0.45, 0.3, 0.45), rotation_z=90, color=C_RGB(60, 60, 60))
        Entity(parent=self.shoulder, model="cube", scale=(0.25, 2.4, 0.25), position=(0, -1.2, 0), color=C_RGB(176, 176, 176))

        self.elbow = Entity(parent=self.shoulder, position=(0, -2.4, 0), rotation_x=self.POSE_IDLE[1])
        Entity(parent=self.elbow, model=Cylinder(resolution=16), scale=(0.35, 0.35, 0.35), rotation_z=90, color=C_RGB(60, 60, 60))
        Entity(parent=self.elbow, model="cube", scale=(0.2, 2.0, 0.2), position=(0, -1.0, 0), color=C_RGB(176, 176, 176))

        self.wrist = Entity(parent=self.elbow, position=(0, -2.0, 0), rotation_x=self.POSE_IDLE[2])
        Entity(parent=self.wrist, model=Cylinder(resolution=16), scale=(0.3, 0.4, 0.3), rotation_z=90, color=C_RGB(60, 60, 60))

        self.scoop = Entity(parent=self.wrist, position=(0, -0.6, 0))
        Entity(parent=self.scoop, model="cube", scale=(1.2, 0.8, 1.0), position=(0, 0, 0), color=C_RGB(200, 160, 30))
        Entity(parent=self.scoop, model="cube", scale=(1.1, 0.7, 0.1), position=(0, 0.05, -0.5), color=C_RGB(30, 30, 30))
        for tx in [-0.45, -0.15, 0.15, 0.45]:
            Entity(parent=self.scoop, model="cube", scale=(0.1, 0.3, 0.15), position=(tx, -0.5, -0.4), color=C_RGB(130, 130, 135))
        try:    wolf_tex = load_texture("wolf_logo.png")
        except: wolf_tex = None
        self.wolf_decal = Entity(parent=self.scoop, model="quad", texture=wolf_tex, scale=(0.6, 0.6), position=(0, 0, 0.51), color=C_RGB(20, 20, 20))

    def _animate_pose(self, pose, duration, delay=0.0, cb=None):
        sv, el, wr = pose
        self.shoulder.animate_rotation_x(sv, duration=duration, delay=delay, curve=curve.in_out_sine)
        self.elbow.animate_rotation_x(el, duration=duration, delay=delay, curve=curve.in_out_sine)
        self.wrist.animate_rotation_x(wr, duration=duration, delay=delay, curve=curve.in_out_sine)
        if cb:
            invoke(cb, delay=delay + duration)

    def dig(self):
        if self.is_busy: return
        self.is_busy = True
        self._animate_pose(self.POSE_LOWER, duration=1.5, delay=0.0)
        self._animate_pose(self.POSE_DIG,   duration=1.2, delay=1.6)
        self._animate_pose(self.POSE_LIFT,  duration=1.5, delay=3.0)
        self._animate_pose(self.POSE_IDLE,  duration=1.0, delay=4.7)
        self._animate_pose(self.POSE_STORE, duration=1.5, delay=5.8, cb=self._unlock)

    def _unlock(self):
        self.is_busy = False
        print("Kazma tamamlandi.")
# ═══════════════════════════════════════════════════════════════════════════════
# ROVER
# ═══════════════════════════════════════════════════════════════════════════════
class TurkiyeRover(Entity):
    def __init__(self):
        super().__init__()
        sx, sz       = 0, 0
        ground_start = surface_y(sx, sz)
        self.position    = Vec3(sx, ground_start + ROVER_GROUND_OFFSET, sz)
        self._wheel_spin = 0.0

        Entity(parent=self, model="cube", scale=(3.2, 0.70, 4.8),  color=C_RGB(72, 78, 88))
        Entity(parent=self, model="cube", scale=(2.9, 0.55, 4.2),  color=C_RGB(55, 60, 70),  position=(0, 0.60, 0))
        Entity(parent=self, model="cube", scale=(3.2, 0.85, 0.25), color=C_RGB(60, 65, 75),  position=(0,  0.1,  2.3), rotation=( 20,0,0))
        Entity(parent=self, model="cube", scale=(3.2, 0.85, 0.25), color=C_RGB(60, 65, 75),  position=(0,  0.1, -2.3), rotation=(-15,0,0))
        Entity(parent=self, model="cube", scale=(0.18, 0.90, 4.6), color=C_RGB(45, 50, 60),  position=(-1.52, 0.30, 0))
        Entity(parent=self, model="cube", scale=(0.18, 0.90, 4.6), color=C_RGB(45, 50, 60),  position=( 1.52, 0.30, 0))
        Entity(parent=self, model="cube", scale=(2.85, 0.10, 4.0), color=C_RGB(50, 55, 65),  position=(0, 0.90, 0))
        
        # Sadece temiz bir aydınlatma ışığı (Açısı yeri güzel aydınlatacak şekilde ayarlandı)
        self.headlight = SpotLight(parent=self, position=(0.0, 1.55, 2.6), rotation=(25, 0, 0), color=color.white)
        
        Entity(parent=self, model="cube", scale=(2.20, 0.55, 0.10), color=C_RGB(210, 35, 42), position=(0, 0.35, 2.38))
        Entity(parent=self, model=Cylinder(resolution=20), scale=(0.32,0.12,0.32), rotation=(90,0,0), color=C_RGB(255,255,255), position=(-0.55,0.38,2.46))
        Entity(parent=self, model=Cylinder(resolution=20), scale=(0.25,0.13,0.25), rotation=(90,0,0), color=C_RGB(210, 35,42),  position=(-0.48,0.38,2.46))
        Entity(parent=self, model="cube", scale=(0.14,0.10,0.14), rotation=(0,0,45), color=C_RGB(255,255,255), position=(-0.22,0.42,2.46))
        Entity(parent=self, model="cube", scale=(0.14,0.10,0.14),                  color=C_RGB(255,255,255), position=(-0.22,0.38,2.46))
        Entity(parent=self, model="cube", scale=(1.10,0.07,0.11),                  color=C_RGB(255,255,255), position=( 0.28,0.35,2.44))
        Entity(parent=self, model="cube", scale=(2.6, 0.50, 0.14), color=C_RGB(50,55,65),        position=(0,1.18, 1.8))
        Entity(parent=self, model="cube", scale=(2.2, 0.35, 0.12), color=C_RGBA(60,140,220,200),  position=(0,1.18, 1.87))
        Entity(parent=self, model="cube", scale=(2.5, 0.12, 0.9),  color=C_RGB(45,50,60),        position=(0,1.45, 1.45), rotation=(-25,0,0))
        Entity(parent=self, model="cube", scale=(2.6, 0.05, 1.6),  color=C_RGB(10,25,100),       position=(0,1.55,-0.5))
        for row in range(6):
            Entity(parent=self, model="cube", scale=(2.62,0.055,0.04), color=C_RGB(5,15,70),  position=(0,1.57,-1.1+row*0.42))
        for col_x in (-0.9,-0.3,0.3,0.9):
            Entity(parent=self, model="cube", scale=(0.04,0.055,1.6),  color=C_RGB(5,15,70),  position=(col_x,1.57,-0.5))
        Entity(parent=self, model="cube", scale=(2.55,0.06,1.55),  color=C_RGBA(30,80,200,80), position=(0,1.56,-0.5))
        Entity(parent=self, model="cube",              scale=(0.10,0.55,0.10), color=C_RGB(180,178,175), position=( 0.8,1.80, 0.5))
        Entity(parent=self, model="sphere",            scale=(0.22,0.22,0.22), color=C_RGB(200,198,195), position=( 0.8,2.12, 0.5))
        Entity(parent=self, model=Cylinder(resolution=16), scale=(0.45,0.06,0.45), color=C_RGB(210,208,205), position=(-0.7,1.90, 0.2))
        Entity(parent=self, model="cube",              scale=(0.06,0.42,0.06), color=C_RGB(185,183,180), position=(-0.7,1.65, 0.2))
        
        Entity(parent=self, model="cube", scale=(0.25,0.20,0.20), color=C_RGB(30,30,35), position=(0,1.55,2.45))
        Entity(parent=self, model=Cylinder(resolution=12), scale=(0.14,0.15,0.14), rotation=(90,0,0), color=C_RGB(20,20,25), position=(0.0,1.55,2.56))
        # Sadece far merceğinin parlak kalmasını sağlayan kod:
        Entity(parent=self, model=Cylinder(resolution=12), scale=(0.10,0.17,0.10), rotation=(90,0,0), color=C_RGB(255,255,245), unlit=True, position=(0.0,1.55,2.58))
        
        Entity(parent=self, model=Cylinder(resolution=8), scale=(0.06, 3.0, 0.06), color=C_RGB(190, 190, 190), position=(-1.2, 0.9, -2.0))
        try:    flag_tex = load_texture("turkish_flag.png")
        except: flag_tex = None
        Entity(parent=self, model="quad", texture=flag_tex,
               color=color.white if flag_tex else color.red,
               scale=(2.0, 1.33), position=(-0.2, 3.2, -2.0), double_sided=True)

        self.arm = RoboticArm(self)

        self.wheels = []
        wheel_positions = [
            (-1.68,  1.85), (-1.68,  0.70), ( 1.68,  1.85), ( 1.68,  0.70),
            (-1.68, -0.70), (-1.68, -1.85), ( 1.68, -0.70), ( 1.68, -1.85),
        ]
        for wx, wz in wheel_positions:
            # Sabit süspansiyon kolu (ana gövdeye bağlı kalır, dönmez)
            Entity(parent=self, model="cube", scale=(0.35,0.08,0.08), color=C_RGB(100,98,95), position=(wx*0.78,-0.18,wz))
            
            # YENİ: Tekerleğin tüm parçalarını tutacak ana grup (Pivot)
            wheel_pivot = Entity(parent=self, position=(wx, -0.35, wz))
            
            # Tüm lastik, jant ve teller artık bu pivot'a (wheel_pivot) bağlanıyor. 
            # (Hepsinin position değeri wheel_pivot'a göre 0,0,0 olduğu için yazmaya gerek yok)
            Entity(parent=wheel_pivot, model=Cylinder(resolution=20), scale=(0.72,0.36,0.72), rotation=(0,0,90), color=C_RGB(28,26,24))
            Entity(parent=wheel_pivot, model=Cylinder(resolution=20), scale=(0.74,0.08,0.74), rotation=(0,0,90), color=C_RGB(120,118,115))
            Entity(parent=wheel_pivot, model=Cylinder(resolution=20), scale=(0.48,0.37,0.48), rotation=(0,0,90), color=C_RGB(85,83,80))
            Entity(parent=wheel_pivot, model=Cylinder(resolution=16), scale=(0.18,0.38,0.18), rotation=(0,0,90), color=C_RGB(150,148,145))
            
            # Tellerin sayısı 12'ye düşürüldü ki dönüş hızı ve açısı gözle rahat algılansın
            for spoke in range(12): 
                Entity(parent=wheel_pivot, model="cube", scale=(0.04,0.62,0.06), color=C_RGB(50,48,45), rotation=(spoke*30, 90, 0))
                
            self.wheels.append(wheel_pivot)

    def update(self):
        dt = time.dt
        if autonomy.active:
            autonomy.update(self, dt)
        ice_tour.update(dt)
        self._update_camera(dt)
        minimap.update_rover(self.x, self.z, self.rotation_y)
        update_hud_info(self)

    def _update_camera(self, dt):
        target_cam_pos = Vec3(self.x, self.y + 20, self.z - 28)
        camera.position = lerp(camera.position, target_cam_pos, 4.0 * dt)
        camera.look_at(self)

# ── HUD ───────────────────────────────────────────────────────────────────────
info_status_text = None
info_pos_text    = None
info_target_text = None
info_speed_text  = None
_dig_warning_bg  = None
_dig_warning_txt = None

def _set_dig_warning(visible):
    if _dig_warning_bg  is not None: _dig_warning_bg.enabled  = visible
    if _dig_warning_txt is not None: _dig_warning_txt.enabled = visible

def create_advanced_hud():
    global info_status_text, info_pos_text, info_target_text, info_speed_text
    global _dig_warning_bg, _dig_warning_txt

    Entity(parent=camera.ui, model="quad", scale=(0.45, 0.60),
           position=(-0.65, 0.20), color=C_RGBA(10, 15, 30, 200))
    try:    logo_tex = load_texture('logo.png')
    except: logo_tex = None
    Entity(parent=camera.ui, model="quad", texture=logo_tex, scale=(0.40, 0.12), position=(-0.65, 0.41), z=-1)
    Text("TURKIYE AY ROVER", parent=camera.ui, position=(-0.82, 0.33), scale=1.3, color=C_RGB(220, 30, 40), z=-1)
    for i, line in enumerate([
        "Sol tik  -> Hedef sec",
        "SPACE    -> Rota baslat",
        "H        -> Buz turu",
        "R        -> Sifirla",
        "ESC      -> Cikis",
    ]):
        Text(line, parent=camera.ui, position=(-0.82, 0.25 - i*0.04),
             scale=1.0, color=C_RGB(200, 210, 255), z=-1)

    info_panel_y = -0.22
    Entity(parent=camera.ui, model="quad", scale=(0.45, 0.22),
           position=(-0.65, info_panel_y), color=C_RGBA(10, 15, 30, 200), z=-0.5)
    Text("ONEMLI BILGILER", parent=camera.ui,
         position=(-0.82, info_panel_y + 0.08), scale=1.1, color=C_RGB(100, 100, 100), z=-1)
    info_status_text = Text("GOREV DURUMU: BEKLIYOR", parent=camera.ui,
                            position=(-0.82, info_panel_y + 0.03), scale=1.0, color=C_RGB(255, 100, 100), z=-1)
    info_pos_text    = Text("KONUM: X=0, Z=0", parent=camera.ui,
                            position=(-0.82, info_panel_y - 0.01), scale=1.0, color=C_RGB(200, 210, 255), z=-1)
    info_target_text = Text("HEDEF: SECILMEDI", parent=camera.ui,
                            position=(-0.82, info_panel_y - 0.05), scale=1.0, color=C_RGB(200, 210, 255), z=-1)
    info_speed_text  = Text("HIZ: 0.0 m/s", parent=camera.ui,
                            position=(-0.82, info_panel_y - 0.09), scale=1.0, color=C_RGB(200, 210, 255), z=-1)

    _dig_warning_bg = Entity(
        parent=camera.ui, model="quad",
        scale=(0.75, 0.08),
        position=(0.0, 0.43),
        color=C_RGBA(0, 60, 140, 230),
        z=-1, enabled=False,
    )
    _dig_warning_txt = Text(
        "KAZMA ISLEMI DEVAM EDIYOR — BUZ ORNEGI TOPLANIYOR",
        parent=camera.ui,
        position=(0.0, 0.43),
        origin=(0, 0),
        scale=1.1,
        color=C_RGB(80, 210, 255),
        z=-2, enabled=False,
    )

def update_hud_info(rover_ent):
    if info_status_text is None: return
    if ice_tour.active:
        s = "Buz Turu: Aktif"
        c = C_RGB(100, 210, 255)
    elif autonomy.active:
        s = "Otonom: Aktif"
        c = C_RGB(80, 220, 120)
    else:
        s = "Otonom: Pasif"
        c = C_RGB(255, 100, 100)
    info_status_text.text  = f"GOREV DURUMU: {s}"
    info_status_text.color = c
    info_pos_text.text = f"KONUM: X={rover_ent.x:.1f}, Z={rover_ent.z:.1f}"
    if minimap.target_wp:
        info_target_text.text  = f"HEDEF: X={minimap.target_wp[0]:.1f}, Z={minimap.target_wp[1]:.1f}"
        info_target_text.color = C_RGB(255, 200, 50)
    else:
        info_target_text.text  = "HEDEF: SECILMEDI"
        info_target_text.color = C_RGB(100, 100, 100)
    if autonomy.active and autonomy.path:
        info_speed_text.text  = f"HIZ: {AutonomyController.MAX_SPEED:.1f} m/s"
        info_speed_text.color = color.white
    else:
        info_speed_text.text  = "HIZ: 0.0 m/s"
        info_speed_text.color = color.white

# ── OLUSTURMA ─────────────────────────────────────────────────────────────────
print("Terrain mesh olusturuluyor...")
ground      = build_terrain_mesh()

rocks_list = []

create_starfield()
create_earth()
create_ice_crystals()

print("A* maliyet haritasi olusturuluyor...")
build_cost_map(features_list, rocks_list)

autonomy = AutonomyController()
ice_tour = IceTourController()
rover    = TurkiyeRover()
create_advanced_hud()

nav_status = Text("Haritadan hedef secin  |  H = Buz Turu",
                  parent=camera.ui, position=(-0.82, -0.42),
                  scale=1.1, color=C_RGB(255, 100, 100))

minimap = MiniMap(features_list, rocks_list)
minimap.update_rover(rover.x, rover.z, rover.rotation_y)

def input(key):
    if key == 'escape':
        application.quit()
    elif key == 'r':
        autonomy.stop()
        ice_tour.stop()
        minimap.reset()
    elif key == 'k':
        rover.arm.dig()
        _set_dig_warning(True)
        invoke(_set_dig_warning, False, delay=7.5)
    elif key == 'h':
        autonomy.stop()
        ice_tour.start(rover.x, rover.z)
    elif key == 'space':
        if minimap.target_wp:
            bx, bz = minimap.target_wp
            nav_status.text  = "A* rota hesaplaniyor..."
            nav_status.color = C_RGB(255, 200, 50)
            sg, si = world_to_grid(rover.x, rover.z)
            eg, ei = world_to_grid(bx, bz)
            final_path = astar(sg, si, eg, ei)
            if final_path:
                minimap.show_path(final_path)
                autonomy.start(final_path, (bx, bz))
                nav_status.text  = f"Otonom: {len(final_path)} wp -> Hedefe gidiliyor..."
                nav_status.color = C_RGB(80, 220, 120)
            else:
                nav_status.text  = "Rota bulunamadi!"
                nav_status.color = color.red
        else:
            nav_status.text  = "Once haritadan hedef secin!"
            nav_status.color = color.red
    elif key == 'left mouse down':
        minimap.handle_click(mouse.x, mouse.y)

print("Hazir! K=Kaz, H=Buz Turu, SPACE=Rota, R=Sifirla")
app.run()