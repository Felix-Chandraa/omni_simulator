# OMNI-Trainer Simulator

Simulator latihan terbang fixed-wing **Omni-Trainer** (DLE30, wingspan kelas trainer)
berbasis **ArduPilot SITL + JSBSim**, dengan ground control station 3D kustom
**Feather Flight** (Cesium) yang menampilkan pesawat di atas citra satelit
Lanud Wiriadinata, Tasikmalaya.

```
┌─────────────────────┐   MAVLink (udp 14550)   ┌──────────────────────┐
│   Feather Flight    │◄────────────────────────►│  ArduPilot SITL      │
│  (PyQt6 + Cesium)   │                          │  (ArduPlane)         │
│  peta 3D, HUD,      │                          │        ▲             │
│  mission, views     │                          │        │ fcs/*-cmd   │
└─────────────────────┘                          │        ▼             │
                                                 │  JSBSim FDM          │
┌─────────────────────┐   MAVLink (tcp 5762)     │  (Omni-Trainer.xml)  │
│ load_default_       │◄────────────────────────►│  fisika + mesin      │
│ mission.py (loader) │                          └──────────────────────┘
└─────────────────────┘
```

---

## 1. Struktur repositori

```
omni_simulator/
├─ setup.sh                  # instalasi satu-perintah utk laptop baru
├─ run_demo.sh               # jalankan SITL (parm & misi default otomatis)
├─ README.md
├─ Feather-Flight-main/      # GCS 3D (PyQt6 + Cesium)
│  ├─ main.py                # entry point (jalankan DARI dalam folder ini)
│  ├─ config.py              # server/port
│  ├─ map.html               # host Cesium
│  ├─ locations/wiriadinata.env   # SATU SUMBER LOKASI (SDD Bab 8)
│  ├─ tools/gen_location_config.py # sebarkan env -> config.js, locations.txt, dll
│  └─ src/
│     ├─ main_window.py, mav_worker.py, server.py, fg_link/ ...
│     └─ js/  (main, config, state, core/{map,camera,views,aircraft,runway,
│              terrain,home,surfaces}, mission/, telemetry/, widgets/,
│              mavlink/, utils/)
└─ omnitrainer-sitl/
   ├─ install.sh             # apt+pip deps & salin aset -> pohon ardupilot
   ├─ launcher.py + omni_launcher/  # GUI launcher (opsional)
   ├─ scripts/
   │  ├─ load_default_mission.py    # auto-upload misi default (idempoten)
   │  ├─ omni_efi_mavlink_sim.py    # telemetri EFI (opsional)
   │  └─ omni_rangefinder_mavlink_sim.py
   ├─ assets/
   │  ├─ missions/wiriadinata_default.txt   # misi default (kotak 6 item)
   │  └─ ardupilot/aircraft/Omni-Trainer/   # SUMBER KEBENARAN model & parm
   │     ├─ Omni-Trainer.xml               # FDM yang DIMUAT JSBSim ★
   │     ├─ Omni-Trainer-JSBSim.xml        # varian FlightGear (TIDAK dimuat SITL)
   │     ├─ omni_trainer_sitl.parm         # parm default (421 baris) ★
   │     ├─ Engines/DLE30_EFI.xml          # mesin (model electric_engine)
   │     └─ reset.xml, Systems/, ...
   └─ ardupilot/             # di-clone oleh setup.sh (TIDAK ikut git)
```

★ = file paling penting; lihat §5.

---

## 2. Instalasi di laptop baru

Prasyarat: Ubuntu 22.04/24.04, internet (clone ardupilot ± beberapa GB).

```bash
git clone <repo-anda> omni_simulator
cd omni_simulator
./setup.sh          # apt deps -> clone ardupilot -> salin aset -> venv -> lokasi
```

`setup.sh` idempoten — aman dijalankan ulang; langkah yang sudah beres dilewati.
Ardupilot sudah ada di tempat lain? `./setup.sh --no-clone` lalu taruh/symlink
repo di `omnitrainer-sitl/ardupilot`.

---

## 3. Menjalankan

### 3.1 SITL

```bash
./run_demo.sh                # backend JSBSim, model Omni-Trainer (default)
./run_demo.sh plane          # backend fisika bawaan ArduPilot (pembanding)
./run_demo.sh jsbsim -w      # wipe eeprom; parm default otomatis termuat ulang
```

Argumen setelah mode diteruskan apa adanya ke `sim_vehicle.py`.
`run_demo.sh` otomatis melakukan dua hal penting:

1. **`--add-param-file`** menunjuk `omni_trainer_sitl.parm` di pohon autotest —
   diterapkan setiap kali eeprom dibuat baru (instalasi segar / `-w`).
2. Menjalankan **loader misi** di latar belakang: menunggu heartbeat
   (tcp 5762, fallback udp 14551), meng-upload misi default **hanya bila
   autopilot belum punya misi** (tidak pernah menimpa misi buatan Anda).
   Log: `/tmp/omni_mission_load.log`.

> ⚠️ **Backend `plane`** ikut memuat parm Omni-Trainer, termasuk
> `RC2/RC4/SERVO2/SERVO4_REVERSED` yang khusus konvensi tanda JSBSim —
> kontrol pitch/yaw bisa terasa terbalik di model bawaan ArduPilot.
> Gunakan hanya sebagai pembanding kasar. Catatan: parameter juga tersimpan
> di `eeprom.bin`, jadi berpindah backend tidak otomatis mengembalikan default.

### 3.2 Feather Flight (GCS)

```bash
source .venv/bin/activate
cd Feather-Flight-main && python main.py
```

Feather Flight konek ke `udp:127.0.0.1:14550` (output MAVProxy).

### 3.3 Terbang pertama

```
# di console MAVProxy:
wp list          # 6 item (misi kotak default)
mode auto
arm throttle     # throttle naik -> ground roll -> rotate -> kotak -> RTL loiter
```

Tanpa misi, gunakan `mode takeoff` (takeoff otomatis tanpa mission plan).

### 3.4 Aset 3D yang harus disalin manual

`Feather-Flight-main/dist/models/` sengaja **kosong** di repo/zip. Salin dua
file berikut dari instalasi/backup Anda sebelum menjalankan GCS:

| File | Fungsi | Bila hilang |
|---|---|---|
| `omni_plane.glb` | model 3D pesawat | pesawat tidak muncul di peta |
| `runway_wiriadinata.png` | tekstur landasan | landasan tampak polos |

Tekstur runway bisa diregenerasi:
`python tools/gen_runway_texture.py --out dist/models/runway_wiriadinata.png`.
Lihat juga `dist/models/README.txt`.

---

## 4. View kamera Feather Flight

| View   | Perilaku |
|--------|----------|
| FPV    | dari hidung pesawat, orientasi = attitude penuh |
| TAIL   | chase di belakang ekor, roll dikunci |
| FOLLOW | trackedEntity klasik |
| GROUND | pengamat statis di darat (posisi GCS), selalu menoleh ke pesawat |
| FREE   | kamera bebas |

**Kontrol GROUND view** (aktif hanya saat view GROUND):

- **Roda mouse** — zoom teropong (FOV 65°→2°, ±32×). Posisi TIDAK berpindah,
  arah tetap terkunci ke pesawat. FOV pulih otomatis saat pindah view.
- **W/S** (atau ↑/↓) — melangkah mendekati / menjauhi pesawat (horizontal).
- **A/D** (atau ←/→) — geser samping. Langkah 2 m; tahan **Shift** = 10 m.
- **R** — reset posisi ke koordinat env + zoom normal.

Posisi start GROUND setiap run = `GCS_LAT/GCS_LON` di
`locations/wiriadinata.env`. Geseran hanya bertahan selama sesi.

**Pencahayaan (P-LIGHT)**: model glTF di Cesium disinari `scene.light`. Agar
pesawat tidak gelap saat SITL dijalankan malam hari, `core/map.js` memasang
**headlight** — lampu directional yang selalu mengikuti arah kamera. Terrain
tidak terpengaruh (`globe.enableLighting = false`).

**Ketahanan Cesium Ion (P-RES)**: terrain dan citra satelit keduanya berasal
dari Cesium Ion. Bila Ion gagal (token dicabut, **kuota bulanan habis**, atau
offline), `core/map.js` otomatis jatuh ke terrain ellipsoid + peta
OpenStreetMap dan menampilkan toast — aplikasi tetap jalan, hanya kehilangan
relief 3D & citra satelit. Cek kuota di https://ion.cesium.com → *Usage*;
ganti token di `src/js/config.js` (`cesiumIonAccessToken`).

---

## 5. Sistem konfigurasi (baca sebelum mengubah apa pun)

### 5.1 `omni_trainer_sitl.parm` — sumber kebenaran parameter

421 baris, dibangun dari **dump penuh pesawat referensi** yang terverifikasi:
diam total sebelum arming, PID hasil tuning, terbang stabil. Isinya:

- **Perilaku terbang & darat** (371 param): PID attitude, TECS, NAVL1, limit,
  airspeed 22 m/s cruise, endpoint RC/servo, `RC2/RC4 + SERVO2/SERVO4
  REVERSED 1` (konvensi tanda FDM), `SERVO3_TRIM/MIN 1000` (anti jalan
  sendiri saat disarmed), mode map, takeoff/landing.
- **Kalibrasi IMU** (26 param): lolos PreArm accel/gyro tanpa `accelsimple`
  manual — ID sensor SITL deterministik, valid di mesin mana pun.
- **Fitur sim**: `EFI_TYPE 9`, `RPM1_TYPE 3` (skrip EFI, opsional);
  **rangefinder default MATI** (`RNGFND1_TYPE 0`) — FDM eksternal tidak
  menyuplai data ke tipe SITL sehingga PreArm memblokir; aktifkan tipe 10 +
  jalankan skripnya bila perlu.
- **Pengaman**: `ARMING_CHECK 1`, `RTL_AUTOLAND 0` (RTL = loiter, bukan
  auto-land), `ARSPD_SKIP_CAL 0`.

Mengubah tuning? Ubah **di file ini** (assets), salin ke autotest (§5.3),
lalu `./run_demo.sh jsbsim -w`. Jangan tuning lewat `param set` lepas yang
tidak dicatat — itu sumber "kok dulu bisa" klasik.

### 5.2 `Omni-Trainer.xml` — FDM yang benar-benar dimuat

⚠️ **JSBSim memuat `Omni-Trainer.xml`, BUKAN `Omni-Trainer-JSBSim.xml`.**
(`load_model('Omni-Trainer')` → `aircraft/Omni-Trainer/Omni-Trainer.xml`.)
Varian `-JSBSim.xml` hanya untuk FlightGear. Edit aero/gear/mesin di file
yang salah = tidak berefek — jebakan yang pernah menghabiskan waktu berjam-jam.

Di dalamnya ada channel **Engine Arm Gate** (flight_control): mesin dimodelkan
`electric_engine` (thrust mengikuti throttle langsung, tanpa idle), dan gerbang
memotong throttle < 3 % menjadi 0 ke mesin — prop dijamin diam saat disarmed,
kebal bocoran throttle kecil. Teruji diferensial: bocor 2 % → diam; 25 % →
meluncur normal.

### 5.3 Alur aset: assets → autotest

File di `assets/` adalah **sumber**; yang dibaca SITL adalah salinannya di
`omnitrainer-sitl/ardupilot/Tools/autotest/aircraft/Omni-Trainer/`.
Setelah mengubah parm/XML di assets, salin:

```bash
cp -a omnitrainer-sitl/assets/ardupilot/aircraft/Omni-Trainer/. \
      omnitrainer-sitl/ardupilot/Tools/autotest/aircraft/Omni-Trainer/
```

(atau `bash omnitrainer-sitl/install.sh` — sudah auto-deteksi ardupilot proyek).
Verifikasi isi, bukan sekadar keberadaan:

```bash
grep PTCH_RATE_P omnitrainer-sitl/ardupilot/Tools/autotest/aircraft/Omni-Trainer/omni_trainer_sitl.parm
# harus: PTCH_RATE_P 0.150000
```

### 5.4 `wiriadinata.env` — satu sumber lokasi

Koordinat spawn, heading runway, posisi GCS, kalibrasi geoid. Jangan tebar
angka ke file lain; `tools/gen_location_config.py` yang menyebarkannya.

---

## 6. Troubleshooting (dari insiden nyata)

| Gejala | Penyebab | Solusi |
|---|---|---|
| `libgl1-mesa-glx has no installation candidate` | nama paket lama (pra-24.04) | sudah dipatch: `libgl1 libglx-mesa0 libegl1` |
| dpkg error `docker-compose-v2` | bentrok dgn docker-ce (`docker-compose-plugin`) | installer kini best-effort: skip bila `docker compose` sudah ada; bila apt macet: `sudo dpkg --remove --force-remove-reinstreq docker-compose-v2 && sudo apt -f install` |
| `Can not perform a '--user' install` | `pip --user` dilarang di dalam venv | installer kini deteksi `VIRTUAL_ENV`; atau `deactivate` dulu |
| `.venv/bin/python: No such file` | venv di ROOT proyek, bukan di Feather-Flight-main; atau setup mati sebelum langkah venv | dari root: `source .venv/bin/activate`; tuntaskan `./setup.sh` |
| `PreArm: 3D Accel calibration needed` | eeprom baru tanpa kalibrasi | parm default sudah memuat kalibrasi; kalau muncul = parm tidak termuat (cek §5.3) |
| `PreArm: Rangefinder 1: No Data` | RNGFND tipe SITL/MAVLink tanpa sumber data | default kini `RNGFND1_TYPE 0`; utk rangefinder: tipe 10 + jalankan skripnya |
| Pesawat **jalan sendiri sebelum arming** | throttle bocor saat disarmed (mis. `SERVO3_TRIM 1500` di eeprom default) | parm memaksa `SERVO3_TRIM/MIN 1000` + gerbang FDM <3 % |
| Prop mati padahal armed + AUTO, surface gerak | **misi kosong** → mission complete → RTL → throttle ditahan di darat (throttle-suppress) | `wp load` misi ber-TAKEOFF, atau `mode takeoff`; loader default menangani ini |
| SITL mati mendadak saat menyentuh tanah (`Connection reset`) | gear model JSBSim meledak numerik pada touchdown berkecepatan | hindari menabrakkan; landing = flare manual; perbaikan gear = pekerjaan FDM tersendiri |
| Pesawat gelap di Cesium | jam scene = jam sistem → malam → model tak tersinari | sudah dipatch: jam dibekukan siang WIB (`core/map.js`) |
| Diedit tapi "tidak ngefek" | (a) edit `Omni-Trainer-JSBSim.xml` (file salah, §5.2); (b) assets belum disalin ke autotest (§5.3) | edit `Omni-Trainer.xml`; salin & verifikasi isi |
| `Arming checks disabled` di log | `ARMING_CHECK 0` tersisa dari `arm uncheck` | `param set ARMING_CHECK 1` (parm default sudah memaksanya) |
| Misi default tidak muncul | loader gagal konek | `cat /tmp/omni_mission_load.log`; manual: `wp load omnitrainer-sitl/assets/missions/wiriadinata_default.txt` |

**Diagnosis "pesawat bergerak" universal** — jalankan saat bergerak:
`status SERVO_OUTPUT_RAW`, `status RC_CHANNELS`, `status VFR_HUD`.
`servo3_raw` > min = ada yang memerintah throttle (cek chan3 utk RC override);
`servo3_raw` = min tapi ikon bergerak dgn groundspeed ~0 = drift tampilan,
bukan gerak fisik.

---

## 7. Catatan pengembangan

- **Venv & dependensi**: semuanya folder-lokal (`.venv`, `omnitrainer-sitl/
  ardupilot`, JSBSim via pip di venv). Dua folder proyek di satu laptop tidak
  saling mengganggu.
- **Parm referensi**: bila menemukan tuning lebih baik di sesi live, `param
  save`, diff terhadap `omni_trainer_sitl.parm`, dan pindahkan perubahan yang
  disengaja ke file — jangan biarkan hidup hanya di eeprom.
- **Feather Flight "future use"**: `mission/upload.js`, `widgets/attitude
  Indicator|headingTape|altitudeTape`, `utils/events.js` disengaja
  dipertahankan untuk fase berikutnya (lihat SDD).
- **File misi**: format QGC WPL 110; default = takeoff + kotak 800×700 m +
  RTL (loiter). Edit di `assets/missions/`, loader hanya meng-upload ke
  autopilot yang misinya kosong.
