# OMNI-Trainer Simulator

Simulator latihan terbang fixed-wing **Omni-Trainer** (DLE30, 15 kg) berbasis
**ArduPilot SITL + JSBSim**, dengan ground control station 3D **Feather Flight**
(PyQt6 + Cesium) di atas citra satelit Lanud Wiriadinata, Tasikmalaya.

```
┌──────────────────────┐  MAVLink udp:14550   ┌────────────────────────┐
│   Feather Flight     │◄────────────────────►│  ArduPilot SITL        │
│   (PyQt6 + Cesium)   │                      │  (ArduPlane)           │
│   :8000 web  :8765 ws│◄──── FGNetFDM ───────┤        ▲               │
└──────────────────────┘      udp:5503        │        │ fcs/*-cmd     │
                                              │        ▼               │
┌──────────────────────┐  MAVLink tcp:5762    │  JSBSim FDM            │
│ load_default_mission │◄────────────────────►│  (Omni-Trainer.xml)    │
└──────────────────────┘                      └────────────────────────┘
```

> **Status dokumen**: seluruh isi README ini diverifikasi langsung terhadap kode
> di repo ini (Juli 2026). Fitur yang **belum** terimplementasi dipisahkan tegas
> di 9 agar tidak tertukar dengan yang sudah berjalan.

---

## 1. Struktur repositori

```
omni_simulator/
├─ setup.sh                  # instalasi satu-perintah untuk laptop baru
├─ run_demo.sh               # jalankan SITL (parm & misi default otomatis)
├─ README.md
├─ Feather-Flight-main/      # GCS 3D
│  ├─ main.py                # entry point (jalankan DARI dalam folder ini)
│  ├─ config.py              # port & konstanta backend
│  ├─ map.html               # host Cesium + markup widget
│  ├─ locations/wiriadinata.env      # SATU sumber kebenaran lokasi
│  ├─ tools/gen_location_config.py   # sebarkan env -> config JS & locations.txt
│  ├─ dist/models/           # KOSONG di repo — lihat 2.3
│  └─ src/
│     ├─ main_window.py, mav_worker.py, server.py, telemetry_bus.py, fg_link/
│     └─ js/  main.js, config.js, state.js, dom.js, bus.js, profile.js, ui.js,
│             core/{map,camera,views,aircraft,home,terrain,runway,surfaces}.js
│             mission/, telemetry/, widgets/, mavlink/, utils/
└─ omnitrainer-sitl/
   ├─ install.sh             # deps + salin aset ke pohon ardupilot
   ├─ launcher.py, omni_launcher/    # GUI launcher (opsional)
   ├─ scripts/
   │  ├─ load_default_mission.py     # auto-upload misi (idempoten)
   │  ├─ omni_efi_mavlink_sim.py     # telemetri EFI (opsional)
   │  └─ omni_rangefinder_mavlink_sim.py
   ├─ assets/
   │  ├─ missions/wiriadinata_default.txt
   │  └─ ardupilot/aircraft/Omni-Trainer/   # SUMBER KEBENARAN model & parm
   │     ├─ Omni-Trainer.xml            # FDM yang DIMUAT JSBSim
   │     ├─ Omni-Trainer-JSBSim.xml     # varian FlightGear (TIDAK dimuat SITL)
   │     ├─ omni_trainer_sitl.parm      # parm default, 404 parameter
   │     └─ Engines/DLE30_EFI.xml, reset.xml, Systems/
   └─ ardupilot/             # di-clone setup.sh — TIDAK ikut git
```

---

## 2. Instalasi di laptop baru

### 2.1 Prasyarat
Linux Mint 22.2 dan koneksi internet (clone ardupilot beberapa GB).

### 2.2 Perintah
```bash
git clone <repo-anda> omni_simulator
cd omni_simulator
./setup.sh          # apt deps -> clone ardupilot -> pasang aset -> venv -> lokasi
```
Idempoten, aman diulang. Sudah punya ardupilot di tempat lain:
`./setup.sh --no-clone`, lalu taruh/symlink repo di `omnitrainer-sitl/ardupilot`.

Urutan kerja `setup.sh`: paket sistem → clone ardupilot (+submodule) →
`install.sh` (menyalin aset Omni-Trainer ke `ardupilot/Tools/autotest/aircraft/`)
→ buat `.venv` + deps Python termasuk JSBSim → daftarkan `Wiriadinata` ke
`~/.config/ardupilot/locations.txt`.

## 3. Menjalankan (dua terminal)

### 3.1 Terminal 1 — SITL
```bash
./run_demo.sh                # backend JSBSim, model Omni-Trainer (default)
./run_demo.sh plane          # backend fisika bawaan ArduPilot (pembanding)
./run_demo.sh jsbsim -w      # wipe eeprom; parm default dimuat ulang otomatis
```
Argumen setelah mode diteruskan apa adanya ke `sim_vehicle.py`.

`run_demo.sh` otomatis melakukan tiga hal: menyertakan `--add-param-file` ke
`omni_trainer_sitl.parm` di pohon autotest (berlaku setiap eeprom dibuat baru);
menjalankan loader misi di latar belakang (log `/tmp/omni_mission_load.log`)
yang meng-upload misi default **hanya bila autopilot belum punya misi**; dan
memasang `trap` pembersih agar loader maupun binary SITL tidak menjadi proses
yatim yang menahan port.

> Backend `plane` ikut memuat parm Omni-Trainer termasuk
> `RC2/RC4/SERVO2/SERVO4_REVERSED` (khusus konvensi tanda JSBSim), sehingga
> kontrol pitch/yaw bisa terasa terbalik. Gunakan sebagai pembanding kasar saja.

**Shutdown**: ketik `exit` di prompt MAVProxy — lebih rapi daripada Ctrl-C.
Ctrl-C sering memunculkan `Fatal Python error: _enter_buffered_busy`; itu
kosmetik (muncul saat MAVProxy sudah dalam proses mati) dan tidak menghilangkan
parameter, karena ArduPilot menulis param ke eeprom saat di-set, bukan saat
keluar. Verifikasi tidak ada sisa proses:
```bash
pgrep -af "arduplane|JSBSim|mavproxy|load_default_mission"
```

### 3.2 Terminal 2 — Feather Flight
```bash
source .venv/bin/activate
cd Feather-Flight-main && python main.py
```
Aplikasi PyQt otomatis membuka `http://127.0.0.1:8000/map.html`.

### 3.3 Terbang pertama
```
wp list          # 6 item (misi kotak default)
mode auto
arm throttle     # throttle naik -> ground roll -> rotate -> kotak -> RTL loiter
```
Tanpa misi, gunakan `mode takeoff` (takeoff otomatis tanpa mission plan).
Penting: **mode AUTO dengan misi kosong langsung "mission complete" → RTL →
throttle ditahan selama di darat**, sehingga prop tidak berputar meski sudah
armed. Itu perilaku normal ArduPlane, bukan kerusakan.

---

## 4. Pemetaan port jaringan

| Port | Protokol | Modul / fungsi |
|---|---|---|
| **5760** | TCP | Listen utama MAVLink instansi ArduPilot SITL |
| **5762** | TCP | Port serial SITL tambahan — dipakai `load_default_mission.py` |
| **14550** | UDP | Keluaran MAVProxy; `mav_worker.py` dan QGroundControl membaca dari sini (`config.py: CONNECTION_CANDIDATES`) |
| **14551** | UDP | Keluaran MAVProxy kedua — fallback loader misi |
| **5503** | UDP | Stream visual native FGNetFDM v24 dari JSBSim (~1200 Hz), diterjemahkan `fg_link` lalu dipublikasi 30 Hz (`FG_STREAM_PORT`, `FG_PUBLISH_HZ`) |
| **8765** | TCP/WS | Telemetry Bus — WebSocket backend Python → frontend JS, mengalirkan state ke semua layar (`TELEMETRY_BUS_PORT`) |
| **8000** | TCP | Static web server Python (`src/server.py`) menyajikan HTML/CSS/JS/GLB (`PORT`) |

Server statis mengirim header `Cache-Control: no-store`, sehingga browser selalu
memuat JS/CSS terbaru. Bila perubahan kode "tidak berefek" di browser padahal
berjalan normal di aplikasi PyQt, itu cache lama — hard reload (Ctrl+Shift+R)
satu kali.

---

## 5. Multi-layar & kontrol tampilan

### 5.1 Membuka layar tambahan
Frontend disajikan sebagai halaman web biasa, jadi bisa dibuka di jendela atau
monitor lain:
```
http://localhost:8000/map.html
```
> Server mengikat `127.0.0.1` (lihat `src/server.py`), jadi secara default hanya
> bisa diakses dari mesin yang sama. Untuk membukanya dari perangkat lain di
> jaringan, ubah bind menjadi `0.0.0.0` lebih dulu.

### 5.2 Mode layout (tiga mode)
Diimplementasikan di `src/js/widgets/layoutMode.js`:

| Mode | Isi |
|---|---|
| `full` | GCS + 3D lengkap (default) |
| `gcs` | Dashboard instrumen fullscreen; peta mati & render di-pause (hemat GPU) |
| `visual` | 3D murni; semua widget default OFF, bisa dinyalakan per-widget |

Cara mengganti: **ikon gear (⚙) di kanan atas** membuka drawer settings. Bisa
juga lewat console browser: `setLayoutMode("gcs")`. Pilihan disimpan di
`localStorage` dengan kunci `ff.layoutMode`.

> **Batasan nyata**: karena persistensinya `localStorage`, semua tab pada browser
> dan profil yang sama berbagi satu mode. Untuk dua layar dengan mode berbeda
> secara bersamaan, gunakan browser yang berbeda (misalnya aplikasi PyQt =
> `full`, Chrome = `gcs`), profil browser berbeda, atau jendela incognito.
> Parameter URL `?layout=` **belum ada** di versi ini — lihat 9.4.

### 5.3 Tombol keyboard — view kamera
Dipetakan di `src/js/main.js` (`KEY_TO_VIEW`):

| Tombol | View | Perilaku |
|---|---|---|
| `1` | FPV | dari hidung pesawat, orientasi mengikuti attitude penuh |
| `2` | TAIL | chase di belakang ekor, roll dikunci |
| `3` | FOLLOW | kamera mengikuti pesawat |
| `4` | GROUND | pengamat statis di titik GCS, selalu menoleh ke pesawat |
| `5` | FREE | kamera bebas |

Tombol diabaikan saat fokus berada di `INPUT` atau `TEXTAREA`.

### 5.4 Kontrol GROUND view (khusus view 4)
- **Roda mouse** — zoom teropong (FOV 65°→2°, sekitar 32×). Posisi pengamat
  **tidak** berpindah dan arah tetap terkunci ke pesawat. FOV pulih otomatis
  saat berpindah view.
- **W/S** (atau ↑/↓) — melangkah mendekat / menjauh dari pesawat.
- **A/D** (atau ←/→) — geser samping. Langkah 2 m; tahan **Shift** = 10 m.
- **R** — reset posisi ke koordinat `wiriadinata.env` dan zoom normal.

Setiap kali aplikasi dibuka, posisi awal selalu titik GCS dari env; hasil
geseran hanya bertahan selama sesi (reload = kembali ke env). Tinggi mata
di-snap ke terrain. Besar langkah dan rentang zoom dapat diubah di
`src/js/config.js` → `views.ground.moveStepMeters` dan `views.ground.zoom`.

### 5.5 Widget yang bisa di-toggle
Lewat drawer gear: `airspeed`, `altitude`, `altitude_gauge`, `armed`,
`attitude_gauge`, `battery`, `fuel`, `groundspeed`, `heading_gauge`, `mode`,
`pose_badge`, `position`, `preflight`, `profile_label`, `satellites`.

---

## 6. Penyesuaian parameter & fitur

### 6.1 Lokasi, spawn pesawat, dan titik pengamat GCS
**File: `Feather-Flight-main/locations/wiriadinata.env`** — satu-satunya sumber
kebenaran geometri landasan.

| Variabel | Fungsi |
|---|---|
| `LAT`, `LON` | koordinat spawn pesawat |
| `HDG_TRUE` | heading spawn (dihitung otomatis dari threshold bila tersedia) |
| `RWY15_LAT/LON`, `RWY33_LAT/LON` | threshold runway; heading dikalkulasi dari sini |
| `GCS_LAT`, `GCS_LON` | posisi pengamat darat (GROUND view) |
| `GCS_ALT_M` | **kosongkan** agar kamera snap ke elevasi terrain Cesium |

Menukar arah hadap RWY 15 ↔ RWY 33: kurangi atau tambah tepat 180° dari heading.

**Wajib setelah setiap edit** — sebarkan nilainya ke config JS dan locations.txt:
```bash
cd Feather-Flight-main
python3 tools/gen_location_config.py locations/wiriadinata.env --write-ardupilot
```

### 6.2 Sensitivitas animasi control surface
**File: `src/js/core/surfaces.js`.** Defleksi permukaan merespons output PWM
ArduPilot secara real-time. Bila terlihat terlalu ekstrem:
```js
export const SURF = {
  maxDeg: { aileron: 60, ruddervator: 60 },   // turunkan misalnya ke 30
  axis:   { aileron_L:"x", aileron_R:"x", ruddervator_L:"z", ruddervator_R:"z", prop:"z" },
  sign:   { aileron_L:1, aileron_R:1, ruddervator_L:1, ruddervator_R:1, prop:1 }, // -1 = balik arah
  mixE: 0.5,             // porsi elevator pada panel V
  mixR: 0.5,             // porsi rudder pada panel V
  discThresholdPct: 15,  // throttle >= ini: bilah prop menjadi disc blur
  rpmVisualFactor: 22    // derajat per frame pada throttle 100% (murni visual)
};
```
Catatan: model ini memakai **ruddervator (V-tail)**, bukan elevator dan rudder
terpisah — karena itu ada `mixE` dan `mixR`.

### 6.3 Perataan landasan (runway flattening)
Mesh terrain Cesium bisa bergelombang di area landasan. Permukaan lanud dibuat
sebagai grid bertekstur yang tiap simpulnya memakai `flattenHeight(terrain)`,
sehingga datar di runway dan melandai menyatu dengan tanah asli di tepi (lihat
blok P5.6 di `src/js/config.js` dan `src/js/core/runway.js`). Tuning ketinggian
dilakukan bertahap (+0,25 m) sampai slab menutupi mesh bergelombang tanpa
terlihat melayang di ujung-ujungnya.

### 6.4 Pencahayaan & ketahanan peta
- **Headlight** (`core/map.js`): model glTF disinari lampu directional yang
  selalu mengikuti arah kamera, sehingga pesawat tidak gelap saat SITL
  dijalankan malam hari. Terrain tidak terpengaruh
  (`globe.enableLighting = false`).
- **Fallback Cesium Ion** (`core/map.js`): terrain dan citra satelit sama-sama
  berasal dari Ion. Bila Ion gagal (token dicabut, **kuota bulanan habis**, atau
  offline), aplikasi otomatis jatuh ke terrain ellipsoid + peta OpenStreetMap
  dan menampilkan toast, alih-alih menggantung. Cek kuota di
  https://ion.cesium.com → *Usage*; ganti token di `src/js/config.js`
  (`cesiumIonAccessToken`).

---

## 7. Parameter SITL — sumber kebenaran

`omnitrainer-sitl/assets/ardupilot/aircraft/Omni-Trainer/omni_trainer_sitl.parm`
(404 parameter) dibangun dari dump penuh pesawat referensi yang terverifikasi
terbang stabil, ditambah blok hasil pengukuran. Kelompok isinya:

- **Perilaku terbang & darat**: PID attitude, TECS, NAVL1, endpoint RC/servo,
  `RC2/RC4 + SERVO2/SERVO4_REVERSED = 1` (konvensi tanda FDM JSBSim), dan
  `SERVO3_TRIM/MIN = 1000` (anti "pesawat jalan sendiri" saat disarmed).
- **Kalibrasi IMU** (26 parameter): lolos PreArm accel/gyro tanpa
  `calibration accelsimple` manual; ID sensor SITL deterministik sehingga tetap
  sah di mesin mana pun.
- **Fitur simulasi**: `EFI_TYPE 9`, `RPM1_TYPE 3`. **Rangefinder default MATI**
  (`RNGFND1_TYPE 0`) karena FDM eksternal tidak menyuplai data ke tipe SITL
  sehingga PreArm memblokir arming. Untuk memakainya: tipe 10 dan jalankan
  `scripts/omni_rangefinder_mavlink_sim.py`.
- **Pengaman**: `ARMING_CHECK 1`, `RTL_AUTOLAND 0` (RTL = loiter, bukan
  auto-land yang berujung crash saat touchdown), `ARSPD_SKIP_CAL 0`.

### 7.1 Batas aerodinamika (diukur langsung dari FDM, Juli 2026)

| Besaran | Nilai |
|---|---|
| Berat / luas sayap | 15,0 kg (147 N) / 0,75 m² |
| Stall sayap datar | **15,3 m/s** |
| Stall bank 35° / 45° / 65° | 16,9 / 18,2 / **23,5** m/s |
| Drag saat jelajah 22 m/s | ~27 N |
| Thrust tersedia 22 m/s, throttle 100% | 63,6 N (margin 2,4×) |
| Laju panjat maksimum teoritis | ~5,5 m/s |

Konsekuensi yang sudah diterapkan ke parm: `AIRSPEED_MIN 18` (1,18× stall —
nilai 10 membiarkan TECS meluruhkan kecepatan sampai stall), `ROLL_LIMIT_DEG 35`
(bank 65° menuntut 23,5 m/s, **di atas** cruise 22 m/s, sehingga setiap belokan
penuh berakhir stall), dan `TECS_CLMB_MAX 3,5` (menuntut 5 m/s menguras seluruh
cadangan tenaga).

### 7.2 Alur aset: assets → autotest
File di `assets/` adalah **sumber**; yang dibaca SITL adalah salinannya di
`omnitrainer-sitl/ardupilot/Tools/autotest/aircraft/Omni-Trainer/`. Setelah
mengubah parm atau XML:
```bash
cp -a omnitrainer-sitl/assets/ardupilot/aircraft/Omni-Trainer/. \
      omnitrainer-sitl/ardupilot/Tools/autotest/aircraft/Omni-Trainer/
# atau: bash omnitrainer-sitl/install.sh   (auto-deteksi ardupilot proyek)
```
Verifikasi **isi**, bukan sekadar keberadaan file:
```bash
grep PTCH_RATE_P omnitrainer-sitl/ardupilot/Tools/autotest/aircraft/Omni-Trainer/omni_trainer_sitl.parm
# harus keluar: PTCH_RATE_P 0.150000
```

### 7.3 FDM: file mana yang benar-benar dimuat
JSBSim memuat **`Omni-Trainer.xml`**, bukan `Omni-Trainer-JSBSim.xml`
(`load_model('Omni-Trainer')` → `aircraft/Omni-Trainer/Omni-Trainer.xml`).
Varian `-JSBSim.xml` hanya untuk FlightGear. Mengedit file yang salah tidak akan
berefek sama sekali — jebakan yang pernah memakan waktu berjam-jam.

Di dalam `Omni-Trainer.xml` ada channel **Engine Arm Gate**: mesin dimodelkan
sebagai `electric_engine` (thrust mengikuti throttle secara langsung, tanpa
idle), dan gerbang memotong throttle di bawah 3 % menjadi 0 sehingga prop
dijamin diam saat disarmed, kebal terhadap bocoran throttle kecil.

---

## 8. Troubleshooting (dari insiden nyata)

| Gejala | Penyebab | Solusi |
|---|---|---|
| `libgl1-mesa-glx has no installation candidate` | nama paket era pra-24.04 | sudah dipatch: `libgl1 libglx-mesa0 libegl1` |
| dpkg error `docker-compose-v2` | bentrok dengan docker-ce (`docker-compose-plugin`) | installer kini best-effort; bila apt macet: `sudo dpkg --remove --force-remove-reinstreq docker-compose-v2 && sudo apt -f install` |
| `Can not perform a '--user' install` | `pip --user` dilarang di dalam venv | installer mendeteksi `VIRTUAL_ENV`; atau `deactivate` dulu |
| `.venv/bin/python: No such file` | venv berada di ROOT proyek, bukan di `Feather-Flight-main` | dari root: `source .venv/bin/activate` |
| `PreArm: 3D Accel calibration needed` | eeprom baru tanpa kalibrasi | parm default memuat kalibrasi; bila tetap muncul berarti parm tidak termuat (7.2) |
| `PreArm: Rangefinder 1: No Data` | rangefinder aktif tanpa sumber data | default `RNGFND1_TYPE 0` |
| Pesawat **jalan sendiri sebelum arming** | throttle bocor saat disarmed (`SERVO3_TRIM 1500` bawaan) | parm memaksa `SERVO3_TRIM/MIN 1000` + gerbang FDM di bawah 3 % |
| Armed + AUTO tapi prop mati, control surface bergerak | misi kosong → RTL → throttle suppressed selama di darat | `wp load` misi ber-TAKEOFF, atau `mode takeoff` |
| Pesawat jatuh sebelum menyelesaikan circuit | `ROLL_LIMIT_DEG 65` (stall 23,5 m/s > cruise) dan `AIRSPEED_MIN` di bawah stall | sudah diperbaiki, lihat 7.1 |
| SITL mati saat menyentuh tanah (`Connection reset`) | solusi gear JSBSim meledak numerik pada touchdown keras | hindari hard landing; perbaikan gear = pekerjaan FDM tersendiri (9.1) |
| Pesawat gelap di Cesium | model glTF tidak tersinari saat jam sistem malam | headlight, lihat 6.4 |
| Perubahan JS tidak terlihat di browser tapi jalan di aplikasi | cache browser | server mengirim `no-store`; hard reload sekali (4) |
| `completion.bash: No such file` tiap membuka terminal | baris peninggalan installer ArduPilot di `~/.bashrc` menunjuk folder lama | edit `~/.bashrc`, jadikan `[ -f "$F" ] && . "$F"` |
| Sudah diedit tapi "tidak ngefek" | file FDM salah (7.3) atau assets belum disalin ke autotest (7.2) | verifikasi isi file di pohon autotest |

**Diagnosis "pesawat bergerak" universal** — saat pesawat bergerak, jalankan
`status SERVO_OUTPUT_RAW`, `status RC_CHANNELS`, dan `status VFR_HUD`.
Bila `servo3_raw` di atas minimum, ada yang memerintahkan throttle (periksa
`chan3_raw` untuk RC override). Bila `servo3_raw` sama dengan minimum tetapi
ikon bergerak sementara groundspeed ~0, itu drift tampilan, bukan gerak fisik.

---

## 9. Belum terimplementasi / rencana pengembangan

### 9.1 Fisika JSBSim 
Sudah berjalan: FDM Omni-Trainer termuat dan terbang, stream FGNetFDM 5503 →
`fg_link` → UI, gerbang mesin, serta batas aerodinamika yang sudah diukur (7.1).

Belum: pipeline JSBSim formal dengan circuit ter-log dan `jumps=0`; sphere
collider + `SimSession` untuk deteksi crash/touchdown yang terkendali — saat ini
touchdown keras dapat membuat solusi landing gear meledak secara numerik dan
mematikan proses SITL; serta audit ulang koefisien aerodinamika terhadap data
pesawat asli. Nilai aero dan gear saat ini adalah baseline yang layak terbang,
**bukan** hasil validasi terhadap penerbangan nyata.

### 9.2 Kontrol dengan controller / HOTAS
Belum ada di kode. Rancangan `src/input_hotas.py` membaca perangkat lewat
**SDL2 (pysdl2) atau evdev** — mana yang mengenali HOTAS tim masih perlu
verifikasi lokal, dengan kriteria hot-plug dan tanpa root. Kalibrasi per-device
disimpan di `hotas_profiles/<vidpid>.json`: pemetaan axis ke channel
(1 = roll, 2 = pitch, 3 = throttle, 4 = yaw), invert, endpoint 1000–2000 µs,
center trim, deadband, dan expo, dilengkapi wizard kalibrasi CLI. Pengiriman
berupa loop 50 Hz `RC_CHANNELS_OVERRIDE` melalui `mav_worker`.

Semantik yang wajib dipatuhi saat implementasi: pada channel 1–8, nilai `0`
berarti **melepas** override kembali ke RC, sedangkan `65535` berarti
**abaikan field** — mempertahankan override sebelumnya, bukan netral. Salah di
titik ini membuat pesawat liar.

### 9.3 Simulasi kondisi darurat
Belum ada panel instruktur. Mekanismenya tidak memerlukan API khusus: SITL
menerima `PARAM_SET` MAVLink secara on-the-fly. Katalog kegagalan yang
direncanakan:

| Skenario | Parameter |
|---|---|
| Engine fail (penuh / parsial) | `SIM_ENGINE_FAIL`, `SIM_ENGINE_MUL` |
| RC / link loss | `SIM_RC_FAIL=1` |
| GPS fail | `SIM_GPS_DISABLE` (lama) ↔ `SIM_GPS1_ENABLE` (baru) — verifikasi versi lokal |
| Battery drop | `SIM_BATT_VOLTAGE` (ramp bertahap) |
| Vibrasi / IMU | `SIM_ACC_RND`, `ACCELx_FAIL` |
| Angin / turbulensi | `SIM_WIND_SPD`, `SIM_WIND_DIR`, `SIM_WIND_TURB` |
| Servo macet | belum terverifikasi; alternatif `SERVOx_FUNCTION=0` |

Peringatan desain yang penting: parameter `SIM_*` **persisten di eeprom
virtual**. Panel instruktur wajib (a) menyimpan snapshot nilai asli sebelum
injeksi, (b) melakukan restore eksplisit saat skenario diakhiri, dan (c)
menyediakan "reset sesi bersih" berupa restart SITL dengan `-w` atau restore
snapshot penuh. Tanpa itu, kegagalan yang di-inject akan terbawa diam-diam ke
sesi berikutnya.

### 9.4 Lainnya 
- **Parameter URL `?layout=<nama>` dan berkas `layouts/*.json`**
  . Saat ini mode layout hanya lewat drawer gear atau
  `setLayoutMode()`, dan disimpan di `localStorage` (5.2).
- **Widget `planner` dan `instructor`** — belum ada di registry widget.
- **Vehicle-agnostic penuh** (fase P2) — konfigurasi masih spesifik
  Omni-Trainer.
- **Upload misi dari UI** (`mission/upload.js`) serta widget tape
  (`attitudeIndicator.js`, `headingTape.js`, `altitudeTape.js`) dan
  `utils/events.js` — kerangkanya ada, sengaja dipertahankan untuk fase
  berikutnya.

---

## 10. Catatan pengembangan

- **Isolasi lingkungan**: `.venv`, `omnitrainer-sitl/ardupilot`, dan JSBSim
  (wheel pip di dalam venv) semuanya folder-lokal, sehingga dua salinan proyek
  di satu laptop tidak saling mengganggu. Yang dibagi hanya
  `~/.config/ardupilot/locations.txt` (idempoten) dan cache `ccache`.
- **Disiplin parameter**: bila menemukan tuning yang lebih baik saat sesi live,
  jalankan `param save`, diff terhadap `omni_trainer_sitl.parm`, lalu pindahkan
  perubahan yang disengaja ke file. Jangan biarkan tuning hidup hanya di eeprom
  — itu sumber klasik keluhan "kok dulu bisa, sekarang tidak".
- **Regresi cepat sebelum commit**: `bash -n` untuk semua `.sh`,
  `python3 -m py_compile` untuk semua `.py`, `node --check` untuk semua `.js`,
  lalu pastikan lima view (keyboard 1–5) masih berfungsi dan GROUND view berada
  di atas permukaan.
- **Keamanan**: `src/js/config.js` memuat token Cesium Ion. Bila repo dibuat
  publik, token itu dapat dibaca siapa pun dan kuota Anda bisa terkuras —
  gunakan repo privat, atau terbitkan token baru yang dibatasi per-asset.
