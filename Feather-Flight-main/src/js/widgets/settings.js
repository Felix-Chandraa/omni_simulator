import { els } from "../dom.js";
import { WIDGETS } from "./registry.js";
import {
  isWidgetVisible,
  setWidgetOverride,
  resetOverrides
} from "../profile.js";
import { setTapeSource, getTapeSource } from "./altitudeTape.js";
import { MODES, setLayoutMode, getLayoutMode } from "./layoutMode.js";

/**
 * Drawer settings:
 * 1. Pemilih MODE LAYOUT (Full / GCS / 3D) — pindah dari topbar.
 * 2. Checklist widget — berlaku di Full & 3D saja; di GCS diganti
 *    keterangan (dashboard tetap).
 * 3. Pemilih sumber altitude tape.
 */

const MODE_LABEL = { full: "Full", gcs: "GCS", visual: "3D" };

function renderModes() {
  const host = els.settingsModes;
  if (!host) {
    return;
  }

  host.textContent = "";
  const group = document.createElement("div");
  group.className = "layout-group drawer-modes";

  for (const m of MODES) {
    const b = document.createElement("button");
    b.className = "btn layout-btn" + (getLayoutMode() === m ? " active" : "");
    b.dataset.layout = m;
    b.textContent = MODE_LABEL[m];
    b.addEventListener("click", () => {
      setLayoutMode(m);
      renderAll(); // segarkan tombol + checklist sesuai mode baru
    });
    group.appendChild(b);
  }

  host.appendChild(group);
}

function renderChecklist() {
  const list = els.settingsList;
  if (!list) {
    return;
  }

  list.textContent = "";

  if (getLayoutMode() === "gcs") {
    const note = document.createElement("div");
    note.className = "settings-note";
    note.textContent =
      "Mode GCS menampilkan dashboard instrumen tetap. " +
      "Checklist widget berlaku di mode Full dan 3D.";
    list.appendChild(note);
    return;
  }

  const groups = [...new Set(WIDGETS.map((w) => w.group))];

  for (const group of groups) {
    const title = document.createElement("div");
    title.className = "settings-section-title";
    title.textContent = group;
    list.appendChild(title);

    for (const w of WIDGETS.filter((x) => x.group === group)) {
      const row = document.createElement("label");
      row.className = "settings-row";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = isWidgetVisible(w.key);
      cb.addEventListener("change", () => {
        setWidgetOverride(w.key, cb.checked);
      });

      const text = document.createElement("span");
      text.textContent = w.label;

      row.appendChild(cb);
      row.appendChild(text);
      list.appendChild(row);
    }
  }
}

function renderAll() {
  renderModes();
  renderChecklist();
  if (els.settingsReset) {
    els.settingsReset.style.display =
      getLayoutMode() === "gcs" ? "none" : "";
  }
}

function setOpen(open) {
  els.settingsDrawer.classList.toggle("open", open);
  els.settingsBackdrop.classList.toggle("open", open);
  if (open) {
    renderAll();
  }
}

export function initSettings() {
  if (!els.settingsBtn || !els.settingsDrawer) {
    return;
  }

  els.settingsBtn.addEventListener("click", () => setOpen(true));
  els.settingsClose.addEventListener("click", () => setOpen(false));
  els.settingsBackdrop.addEventListener("click", () => setOpen(false));

  els.settingsReset.addEventListener("click", () => {
    resetOverrides();
    renderChecklist();
  });

  if (els.tapeSourceSel) {
    els.tapeSourceSel.value = getTapeSource();
    els.tapeSourceSel.addEventListener("change", () => {
      const src = els.tapeSourceSel.value;
      setTapeSource(src);
      try {
        localStorage.setItem("ff.tapeSource", src);
      } catch (_e) { /* abaikan */ }
    });
  }
}
