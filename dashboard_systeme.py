import tkinter as tk
from tkinter import ttk
import psutil
import platform
from datetime import datetime, timedelta
import threading
import time

# ─────────────────────────────────────────────
#  Palette de couleurs
# ─────────────────────────────────────────────
BG_DARK       = "#0f1117"
BG_CARD       = "#1a1d27"
BG_CARD2      = "#21253a"
ACCENT_BLUE   = "#4f8ef7"
ACCENT_GREEN  = "#3ecf8e"
ACCENT_ORANGE = "#f5a623"
ACCENT_RED    = "#f25f5c"
TEXT_PRIMARY  = "#e8eaf6"
TEXT_MUTED    = "#7c85a2"
BORDER        = "#2a2f45"

FONT_TITLE  = ("Segoe UI", 11, "bold")
FONT_LABEL  = ("Segoe UI", 9)
FONT_VALUE  = ("Segoe UI", 10, "bold")
FONT_SMALL  = ("Segoe UI", 8)
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_MONO   = ("Consolas", 9)

# ─────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────
def fmt_bytes(b):
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} Po"

def fmt_uptime(seconds):
    td = timedelta(seconds=int(seconds))
    h, rem = divmod(td.seconds, 3600)
    m, s   = divmod(rem, 60)
    return f"{td.days}j {h:02d}:{m:02d}:{s:02d}"

def color_for_pct(pct):
    if pct < 60:  return ACCENT_GREEN
    if pct < 85:  return ACCENT_ORANGE
    return ACCENT_RED

# ─────────────────────────────────────────────
#  Barre de progression custom (canvas)
# ─────────────────────────────────────────────
class ProgressBar(tk.Canvas):
    def __init__(self, parent, width=440, height=8, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=BG_CARD, highlightthickness=0, **kw)
        self._width = width
        self._height = height
        self.create_rectangle(0, 0, width, height, fill=BORDER, outline="")
        self._bar = self.create_rectangle(0, 0, 0, height, fill=ACCENT_BLUE, outline="")

    def set(self, pct, color=None):
        pct = max(0, min(100, pct))
        w = int(self._width * pct / 100)
        fill = color or color_for_pct(pct)
        self.coords(self._bar, 0, 0, w, self._height)
        self.itemconfig(self._bar, fill=fill)

# ─────────────────────────────────────────────
#  Carte décorative
# ─────────────────────────────────────────────
class Card(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_CARD,
                         highlightbackground=BORDER, highlightthickness=1, **kw)

# ─────────────────────────────────────────────
#  Application principale
# ─────────────────────────────────────────────
class DashboardSysteme:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SysMonitor  ·  {platform.node()}")
        self.root.geometry("680x640")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(True, True)

        self._net_prev = psutil.net_io_counters()
        self._net_time = time.time()
        self._ts_running = False   # anti-chevauchement Timeshift
        self._ts_tick    = 0       # compteur de cycles

        self._build_header()
        self._build_tabs()
        self._schedule_update()
        self.root.after(3000, self._launch_timeshift_now)  # 1er refresh Timeshift après 3s

    # ── En-tête ──────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=BG_DARK)
        hdr.pack(fill="x", padx=20, pady=(14, 4))

        tk.Label(hdr, text="⬡  SysMonitor", font=("Segoe UI", 16, "bold"),
                 fg=ACCENT_BLUE, bg=BG_DARK).pack(side="left")

        right = tk.Frame(hdr, bg=BG_DARK)
        right.pack(side="right")
        self.lbl_time = tk.Label(right, text="", font=FONT_MONO,
                                  fg=TEXT_MUTED, bg=BG_DARK)
        self.lbl_time.pack()
        self.lbl_uptime = tk.Label(right, text="", font=FONT_SMALL,
                                    fg=TEXT_MUTED, bg=BG_DARK)
        self.lbl_uptime.pack()

        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(fill="x", padx=20, pady=(6, 0))

    # ── Onglets ───────────────────────────────
    def _build_tabs(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",           background=BG_DARK,   borderwidth=0)
        style.configure("TNotebook.Tab",       background=BG_CARD2,  foreground=TEXT_MUTED,
                        font=FONT_LABEL, padding=[16, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", BG_DARK)],
                  foreground=[("selected", TEXT_PRIMARY)])

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=20, pady=12)

        self.tab_vue    = tk.Frame(nb, bg=BG_DARK)
        self.tab_cpu    = tk.Frame(nb, bg=BG_DARK)
        self.tab_mem    = tk.Frame(nb, bg=BG_DARK)
        self.tab_disk   = tk.Frame(nb, bg=BG_DARK)
        self.tab_net    = tk.Frame(nb, bg=BG_DARK)
        self.tab_sys    = tk.Frame(nb, bg=BG_DARK)

        nb.add(self.tab_vue,  text="  Vue d'ensemble  ")
        nb.add(self.tab_cpu,  text="  CPU  ")
        nb.add(self.tab_mem,  text="  Mémoire  ")
        nb.add(self.tab_disk, text="  Disques  ")
        nb.add(self.tab_net,  text="  Réseau  ")
        nb.add(self.tab_sys,  text="  Système  ")

        self._build_overview()
        self._build_cpu_tab()
        self._build_mem_tab()
        self._build_disk_tab()
        self._build_net_tab()
        self._build_sys_tab()

    # ══════════════════════════════════════════
    #  VUE D'ENSEMBLE
    # ══════════════════════════════════════════
    def _build_overview(self):
        p = self.tab_vue
        grid = tk.Frame(p, bg=BG_DARK)
        grid.pack(fill="both", expand=True, pady=10)

        def mini_card(parent, title, accent):
            c = Card(parent)
            c.pack(fill="x", pady=5, padx=4)
            tk.Label(c, text=title, font=FONT_SMALL, fg=accent, bg=BG_CARD).pack(anchor="w", padx=12, pady=(8,2))
            lbl = tk.Label(c, text="—", font=FONT_VALUE, fg=TEXT_PRIMARY, bg=BG_CARD)
            lbl.pack(anchor="w", padx=12)
            bar = ProgressBar(c, width=600)
            bar.pack(padx=12, pady=(4, 10))
            return lbl, bar

        self.ov_cpu_lbl, self.ov_cpu_bar  = mini_card(grid, "● CPU", ACCENT_BLUE)
        self.ov_ram_lbl, self.ov_ram_bar  = mini_card(grid, "● RAM", ACCENT_GREEN)
        self.ov_dsk_lbl, self.ov_dsk_bar  = mini_card(grid, "● Disque (/)", ACCENT_ORANGE)

        # ligne réseau rapide
        net_card = Card(grid)
        net_card.pack(fill="x", pady=5, padx=4)
        tk.Label(net_card, text="● Réseau (débit instantané)", font=FONT_SMALL,
                 fg=ACCENT_BLUE, bg=BG_CARD).pack(anchor="w", padx=12, pady=(8,2))
        self.ov_net_lbl = tk.Label(net_card, text="—", font=FONT_VALUE,
                                    fg=TEXT_PRIMARY, bg=BG_CARD)
        self.ov_net_lbl.pack(anchor="w", padx=12, pady=(0,10))

    # ══════════════════════════════════════════
    #  CPU
    # ══════════════════════════════════════════
    def _build_cpu_tab(self):
        p = self.tab_cpu

        info_card = Card(p)
        info_card.pack(fill="x", pady=(10,4), padx=4)
        info = tk.Frame(info_card, bg=BG_CARD)
        info.pack(fill="x", padx=14, pady=10)
        self.cpu_info_lbl = tk.Label(info, text="", font=FONT_MONO,
                                      fg=TEXT_MUTED, bg=BG_CARD, justify="left")
        self.cpu_info_lbl.pack(anchor="w")

        usage_card = Card(p)
        usage_card.pack(fill="x", pady=4, padx=4)
        tk.Label(usage_card, text="Utilisation globale", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,2))
        self.cpu_total_lbl = tk.Label(usage_card, text="0%", font=("Segoe UI", 22, "bold"),
                                       fg=ACCENT_BLUE, bg=BG_CARD)
        self.cpu_total_lbl.pack(anchor="w", padx=14)
        self.cpu_total_bar = ProgressBar(usage_card, width=620)
        self.cpu_total_bar.pack(padx=14, pady=(4,12))

        core_card = Card(p)
        core_card.pack(fill="both", expand=True, pady=4, padx=4)
        tk.Label(core_card, text="Utilisation par cœur", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,4))

        scroll_frame = tk.Frame(core_card, bg=BG_CARD)
        scroll_frame.pack(fill="both", expand=True, padx=14, pady=(0,10))

        self.core_bars = []
        count = psutil.cpu_count(logical=True)
        cols = 2
        for i in range(count):
            row, col = divmod(i, cols)
            cell = tk.Frame(scroll_frame, bg=BG_CARD)
            cell.grid(row=row, column=col, padx=6, pady=3, sticky="ew")
            scroll_frame.columnconfigure(col, weight=1)
            tk.Label(cell, text=f"Core {i}", font=FONT_SMALL,
                     fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
            bar = ProgressBar(cell, width=280, height=6)
            bar.pack(fill="x")
            lbl = tk.Label(cell, text="0%", font=FONT_SMALL,
                            fg=TEXT_PRIMARY, bg=BG_CARD)
            lbl.pack(anchor="e")
            self.core_bars.append((bar, lbl))

    # ══════════════════════════════════════════
    #  MÉMOIRE
    # ══════════════════════════════════════════
    def _build_mem_tab(self):
        p = self.tab_mem

        ram_card = Card(p)
        ram_card.pack(fill="x", pady=(10,4), padx=4)
        tk.Label(ram_card, text="RAM — Mémoire physique", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,2))
        self.ram_big_lbl = tk.Label(ram_card, text="0 Go", font=("Segoe UI", 22, "bold"),
                                     fg=ACCENT_GREEN, bg=BG_CARD)
        self.ram_big_lbl.pack(anchor="w", padx=14)
        self.ram_bar = ProgressBar(ram_card, width=620)
        self.ram_bar.pack(padx=14, pady=(4,4))
        self.ram_detail_lbl = tk.Label(ram_card, text="", font=FONT_MONO,
                                        fg=TEXT_MUTED, bg=BG_CARD)
        self.ram_detail_lbl.pack(anchor="w", padx=14, pady=(2,10))

        swap_card = Card(p)
        swap_card.pack(fill="x", pady=4, padx=4)
        tk.Label(swap_card, text="SWAP — Mémoire virtuelle", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,2))
        self.swap_big_lbl = tk.Label(swap_card, text="0 Go", font=("Segoe UI", 22, "bold"),
                                      fg=ACCENT_ORANGE, bg=BG_CARD)
        self.swap_big_lbl.pack(anchor="w", padx=14)
        self.swap_bar = ProgressBar(swap_card, width=620)
        self.swap_bar.pack(padx=14, pady=(4,4))
        self.swap_detail_lbl = tk.Label(swap_card, text="", font=FONT_MONO,
                                         fg=TEXT_MUTED, bg=BG_CARD)
        self.swap_detail_lbl.pack(anchor="w", padx=14, pady=(2,10))

    # ══════════════════════════════════════════
    #  DISQUES
    # ══════════════════════════════════════════
    TIMESHIFT_PATH = "/timeshift/snapshots"

    def _build_disk_tab(self):
        p = self.tab_disk
        self.disk_container = tk.Frame(p, bg=BG_DARK)
        self.disk_container.pack(fill="both", expand=True, pady=(10, 4))
        self.disk_widgets = {}

        # ── Carte Timeshift (toujours visible, fixe en bas) ──
        ts_card = Card(p)
        ts_card.pack(fill="x", pady=(4, 10), padx=4)

        hdr = tk.Frame(ts_card, bg=BG_CARD)
        hdr.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(hdr, text="🕐  Timeshift — Snapshots", font=FONT_TITLE,
                 fg=ACCENT_BLUE, bg=BG_CARD).pack(side="left")
        self.ts_badge = tk.Label(hdr, text="", font=FONT_SMALL,
                                  fg=BG_DARK, bg=ACCENT_BLUE, padx=6, pady=1)
        self.ts_badge.pack(side="left", padx=8)

        self.ts_path_lbl = tk.Label(ts_card, text=self.TIMESHIFT_PATH, font=FONT_MONO,
                                     fg=TEXT_MUTED, bg=BG_CARD)
        self.ts_path_lbl.pack(anchor="w", padx=14)

        self.ts_size_lbl = tk.Label(ts_card, text="—", font=("Segoe UI", 16, "bold"),
                                     fg=TEXT_PRIMARY, bg=BG_CARD)
        self.ts_size_lbl.pack(anchor="w", padx=14, pady=(4, 2))

        self.ts_bar = ProgressBar(ts_card, width=620)
        self.ts_bar.pack(padx=14, pady=(2, 4))

        self.ts_detail_lbl = tk.Label(ts_card, text="", font=FONT_MONO,
                                       fg=TEXT_MUTED, bg=BG_CARD)
        self.ts_detail_lbl.pack(anchor="w", padx=14)

        # Liste des snapshots
        self.ts_list_frame = tk.Frame(ts_card, bg=BG_CARD)
        self.ts_list_frame.pack(fill="x", padx=14, pady=(6, 10))
        self.ts_snap_labels = []

    def _refresh_timeshift(self):
        import os, shutil
        path = self.TIMESHIFT_PATH
        if not os.path.isdir(path):
            self.ts_size_lbl.config(text="Dossier introuvable", fg=ACCENT_RED)
            self.ts_badge.config(text="N/A", bg=ACCENT_RED)
            self.ts_detail_lbl.config(text=path)
            self.ts_bar.set(0)
            return

        # Nombre de snapshots (sous-dossiers directs)
        try:
            snapshots = sorted([
                d for d in os.listdir(path)
                if os.path.isdir(os.path.join(path, d))
            ], reverse=True)
            count = len(snapshots)
        except PermissionError:
            self.ts_size_lbl.config(text="Permission refusée", fg=ACCENT_RED)
            self.ts_badge.config(text="⚠", bg=ACCENT_RED)
            return

        # Taille totale du dossier (du avec os.walk)
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass
        except PermissionError:
            total_size = -1

        # Quota : % du système de fichiers parent
        try:
            disk = shutil.disk_usage(path)
            pct = (total_size / disk.total * 100) if total_size >= 0 and disk.total > 0 else 0
        except Exception:
            disk = None
            pct = 0

        # Badge nombre de snapshots
        self.ts_badge.config(
            text=f"{count} snapshot{'s' if count != 1 else ''}",
            bg=ACCENT_BLUE if count > 0 else TEXT_MUTED
        )

        size_str = fmt_bytes(total_size) if total_size >= 0 else "Taille inconnue"
        self.ts_size_lbl.config(
            text=f"{size_str}  ({pct:.1f}% du disque)",
            fg=color_for_pct(pct)
        )
        self.ts_bar.set(pct, color_for_pct(pct))

        if disk:
            self.ts_detail_lbl.config(
                text=f"Disque total : {fmt_bytes(disk.total)}   "
                     f"Libre : {fmt_bytes(disk.free)}   "
                     f"Snapshots occupés : {size_str}"
            )

        # Liste des 5 derniers snapshots
        for w in self.ts_snap_labels:
            w.destroy()
        self.ts_snap_labels = []

        if snapshots:
            sep = tk.Frame(self.ts_list_frame, bg=BORDER, height=1)
            sep.pack(fill="x", pady=(0, 4))
            self.ts_snap_labels.append(sep)

            header = tk.Label(self.ts_list_frame,
                              text=f"{'Snapshot':<35}{'Taille':>12}",
                              font=FONT_MONO, fg=TEXT_MUTED, bg=BG_CARD)
            header.pack(anchor="w")
            self.ts_snap_labels.append(header)

            for snap in snapshots[:5]:
                snap_path = os.path.join(path, snap)
                snap_size = 0
                try:
                    for dirpath, _, files in os.walk(snap_path):
                        for f in files:
                            try:
                                snap_size += os.path.getsize(os.path.join(dirpath, f))
                            except OSError:
                                pass
                except PermissionError:
                    snap_size = -1

                sz = fmt_bytes(snap_size) if snap_size >= 0 else "—"
                row = tk.Frame(self.ts_list_frame, bg=BG_CARD)
                row.pack(fill="x", pady=1)
                self.ts_snap_labels.append(row)
                tk.Label(row, text=f"📁  {snap}", font=FONT_MONO,
                         fg=TEXT_PRIMARY, bg=BG_CARD).pack(side="left")
                tk.Label(row, text=sz, font=FONT_MONO,
                         fg=ACCENT_ORANGE, bg=BG_CARD).pack(side="right")

            if count > 5:
                more = tk.Label(self.ts_list_frame,
                                text=f"  … et {count - 5} autre(s)",
                                font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_CARD)
                more.pack(anchor="w", pady=(2, 0))
                self.ts_snap_labels.append(more)

    def _refresh_disk_tab(self):
        try:
            partitions = psutil.disk_partitions(all=False)
        except Exception:
            return

        seen = set()
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except PermissionError:
                continue

            mp = part.mountpoint
            seen.add(mp)
            pct = usage.percent

            if mp not in self.disk_widgets:
                card = Card(self.disk_container)
                card.pack(fill="x", pady=5, padx=4)
                tk.Label(card, text=f"💾  {mp}", font=FONT_TITLE,
                         fg=ACCENT_ORANGE, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,2))
                tk.Label(card, text=f"{part.fstype}  ·  {part.device}", font=FONT_SMALL,
                         fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w", padx=14)
                big_lbl = tk.Label(card, text="", font=("Segoe UI", 18, "bold"),
                                   fg=TEXT_PRIMARY, bg=BG_CARD)
                big_lbl.pack(anchor="w", padx=14)
                bar = ProgressBar(card, width=620)
                bar.pack(padx=14, pady=(4,4))
                detail = tk.Label(card, text="", font=FONT_MONO, fg=TEXT_MUTED, bg=BG_CARD)
                detail.pack(anchor="w", padx=14, pady=(2,10))
                self.disk_widgets[mp] = (big_lbl, bar, detail)

            big_lbl, bar, detail = self.disk_widgets[mp]
            big_lbl.config(text=f"{pct:.1f}%  utilisé")
            bar.set(pct)
            detail.config(text=f"Utilisé : {fmt_bytes(usage.used)}   Libre : {fmt_bytes(usage.free)}   Total : {fmt_bytes(usage.total)}")

        # Refresh Timeshift toutes les 60s seulement, et jamais en parallèle
        self._ts_tick += 1
        if self._ts_tick >= 40 and not self._ts_running:  # 40 x 1.5s = ~60s
            self._ts_tick = 0
            self._ts_running = True
            threading.Thread(target=self._refresh_timeshift_threaded, daemon=True).start()

    def _refresh_timeshift_threaded(self):
        """Calcule les infos Timeshift via subprocess (contourne les droits root)."""
        import os, shutil, subprocess
        path = self.TIMESHIFT_PATH
        result = {"ok": False}

        # 1. Verifier existence (accessible sans droits en general)
        exists = os.path.exists(path)
        if not exists:
            try:
                r = subprocess.run(["sudo", "-n", "test", "-d", path],
                                   capture_output=True, timeout=3)
                exists = (r.returncode == 0)
            except Exception:
                pass

        if not exists:
            result["error"] = f"Dossier introuvable : {path}"
            self.root.after(0, lambda r=result: self._apply_timeshift_ui(r))
            return

        # 2. Lister les snapshots via sudo -n ls
        snapshots = []
        try:
            r = subprocess.run(
                ["sudo", "-n", "ls", "-1", path],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                snapshots = sorted(
                    [l.strip() for l in r.stdout.splitlines() if l.strip()],
                    reverse=True
                )
            else:
                # Fallback sans sudo
                try:
                    snapshots = sorted(
                        [d for d in os.listdir(path)
                         if os.path.isdir(os.path.join(path, d))],
                        reverse=True
                    )
                except PermissionError:
                    result["error"] = "Permission refusee - ajoutez une regle sudoers NOPASSWD"
                    self.root.after(0, lambda r=result: self._apply_timeshift_ui(r))
                    return
        except Exception as e:
            result["error"] = f"Erreur listing : {e}"
            self.root.after(0, lambda r=result: self._apply_timeshift_ui(r))
            return

        # 3. Taille totale via sudo -n du -sb
        total_size = -1
        try:
            r = subprocess.run(
                ["sudo", "-n", "du", "-sb", path],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0 and r.stdout.strip():
                total_size = int(r.stdout.split()[0])
        except Exception:
            pass

        # 4. Taille par snapshot
        snap_sizes = []
        for snap in snapshots:
            snap_path = os.path.join(path, snap)
            sz = -1
            try:
                r = subprocess.run(
                    ["sudo", "-n", "du", "-sb", snap_path],
                    capture_output=True, text=True, timeout=20
                )
                if r.returncode == 0 and r.stdout.strip():
                    sz = int(r.stdout.split()[0])
            except Exception:
                pass
            snap_sizes.append((snap, sz))

        # 5. Quota disque parent
        try:
            disk = shutil.disk_usage(path)
            pct = (total_size / disk.total * 100) if total_size >= 0 and disk.total > 0 else 0
            disk_info = (disk.total, disk.free)
        except Exception:
            pct = 0
            disk_info = None

        result = {
            "ok": True,
            "snapshots": snapshots,
            "snap_sizes": snap_sizes,
            "total_size": total_size,
            "pct": pct,
            "disk_info": disk_info,
        }
        self._ts_running = False
        self.root.after(0, lambda r=result: self._apply_timeshift_ui(r))

    def _apply_timeshift_ui(self, r):
        if not r.get("ok"):
            msg = r.get("error", "Erreur inconnue")
            self.ts_size_lbl.config(text=msg, fg=ACCENT_RED)
            self.ts_badge.config(text="N/A", bg=ACCENT_RED)
            self.ts_bar.set(0)
            return

        snapshots  = r["snapshots"]
        snap_sizes = r["snap_sizes"]
        total_size = r["total_size"]
        pct        = r["pct"]
        disk_info  = r["disk_info"]
        count      = len(snapshots)

        self.ts_badge.config(
            text=f"{count} snapshot{'s' if count != 1 else ''}",
            bg=ACCENT_BLUE if count > 0 else TEXT_MUTED
        )
        size_str = fmt_bytes(total_size)
        self.ts_size_lbl.config(
            text=f"{size_str}  ({pct:.1f}% du disque)",
            fg=color_for_pct(pct)
        )
        self.ts_bar.set(pct, color_for_pct(pct))

        if disk_info:
            self.ts_detail_lbl.config(
                text=f"Disque total : {fmt_bytes(disk_info[0])}   "
                     f"Libre : {fmt_bytes(disk_info[1])}   "
                     f"Snapshots : {size_str}"
            )

        # Reconstruire la liste
        for w in self.ts_snap_labels:
            w.destroy()
        self.ts_snap_labels = []

        if snap_sizes:
            sep = tk.Frame(self.ts_list_frame, bg=BORDER, height=1)
            sep.pack(fill="x", pady=(0, 4))
            self.ts_snap_labels.append(sep)

            header = tk.Label(self.ts_list_frame,
                              text=f"Derniers snapshots ({min(5, count)}/{count} affichés)",
                              font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_CARD)
            header.pack(anchor="w", pady=(0, 2))
            self.ts_snap_labels.append(header)

            import os
            for snap, snap_size in snap_sizes[:5]:
                sz = fmt_bytes(snap_size) if snap_size >= 0 else "—"
                row = tk.Frame(self.ts_list_frame, bg=BG_CARD)
                row.pack(fill="x", pady=1)
                self.ts_snap_labels.append(row)
                tk.Label(row, text=f"📁  {snap}", font=FONT_MONO,
                         fg=TEXT_PRIMARY, bg=BG_CARD).pack(side="left")
                tk.Label(row, text=sz, font=FONT_MONO,
                         fg=ACCENT_ORANGE, bg=BG_CARD).pack(side="right")

            if count > 5:
                more = tk.Label(self.ts_list_frame,
                                text=f"  … et {count - 5} autre(s) non affichés",
                                font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_CARD)
                more.pack(anchor="w", pady=(2, 0))
                self.ts_snap_labels.append(more)

    # ══════════════════════════════════════════
    #  RÉSEAU
    # ══════════════════════════════════════════
    def _build_net_tab(self):
        p = self.tab_net

        speed_card = Card(p)
        speed_card.pack(fill="x", pady=(10,4), padx=4)
        tk.Label(speed_card, text="Débit instantané", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,2))
        row = tk.Frame(speed_card, bg=BG_CARD)
        row.pack(fill="x", padx=14, pady=(0,10))
        self.net_up_lbl   = tk.Label(row, text="↑  0 Ko/s", font=("Segoe UI", 14, "bold"),
                                      fg=ACCENT_ORANGE, bg=BG_CARD)
        self.net_up_lbl.pack(side="left", padx=(0,30))
        self.net_down_lbl = tk.Label(row, text="↓  0 Ko/s", font=("Segoe UI", 14, "bold"),
                                      fg=ACCENT_GREEN, bg=BG_CARD)
        self.net_down_lbl.pack(side="left")

        total_card = Card(p)
        total_card.pack(fill="x", pady=4, padx=4)
        tk.Label(total_card, text="Totaux depuis le démarrage", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,2))
        row2 = tk.Frame(total_card, bg=BG_CARD)
        row2.pack(fill="x", padx=14, pady=(0,10))
        self.net_sent_lbl = tk.Label(row2, text="📤 Envoyé : 0 Mo", font=FONT_VALUE,
                                      fg=TEXT_MUTED, bg=BG_CARD)
        self.net_sent_lbl.pack(side="left", padx=(0,30))
        self.net_recv_lbl = tk.Label(row2, text="📥 Reçu : 0 Mo", font=FONT_VALUE,
                                      fg=TEXT_MUTED, bg=BG_CARD)
        self.net_recv_lbl.pack(side="left")

        iface_card = Card(p)
        iface_card.pack(fill="both", expand=True, pady=4, padx=4)
        tk.Label(iface_card, text="Interfaces réseau", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,4))
        self.iface_frame = tk.Frame(iface_card, bg=BG_CARD)
        self.iface_frame.pack(fill="x", padx=14, pady=(0,10))
        self._build_iface_list()

    def _build_iface_list(self):
        for w in self.iface_frame.winfo_children():
            w.destroy()
        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
        except Exception:
            return
        for name, addr_list in addrs.items():
            st = stats.get(name)
            up = "🟢 Actif" if (st and st.isup) else "🔴 Inactif"
            ips = [a.address for a in addr_list if a.family.name in ("AF_INET", "AF_INET6")]
            ip_str = "  ".join(ips) if ips else "—"
            row = tk.Frame(self.iface_frame, bg=BG_CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{up}  {name}", font=FONT_LABEL,
                     fg=TEXT_PRIMARY, bg=BG_CARD, width=22, anchor="w").pack(side="left")
            tk.Label(row, text=ip_str, font=FONT_MONO,
                     fg=TEXT_MUTED, bg=BG_CARD).pack(side="left", padx=10)

    # ══════════════════════════════════════════
    #  SYSTÈME
    # ══════════════════════════════════════════
    def _build_sys_tab(self):
        p = self.tab_sys

        card = Card(p)
        card.pack(fill="x", pady=(10,4), padx=4)
        tk.Label(card, text="Informations système", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,4))

        uname = platform.uname()
        rows = [
            ("Hôte",          uname.node),
            ("Système",       f"{uname.system} {uname.release}"),
            ("Version",       uname.version[:60]),
            ("Architecture",  uname.machine),
            ("Processeur",    uname.processor[:60] or platform.processor()[:60]),
            ("Cœurs phys.",   str(psutil.cpu_count(logical=False))),
            ("Cœurs logiques",str(psutil.cpu_count(logical=True))),
            ("Python",        platform.python_version()),
        ]
        for label, val in rows:
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", padx=14, pady=1)
            tk.Label(row, text=label, font=FONT_LABEL, fg=TEXT_MUTED,
                     bg=BG_CARD, width=18, anchor="w").pack(side="left")
            tk.Label(row, text=val,   font=FONT_MONO,  fg=TEXT_PRIMARY,
                     bg=BG_CARD, anchor="w").pack(side="left")
        tk.Label(card, text="", bg=BG_CARD).pack()  # padding bas

        temp_card = Card(p)
        temp_card.pack(fill="x", pady=4, padx=4)
        tk.Label(temp_card, text="Températures", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w", padx=14, pady=(10,4))
        self.temp_frame = tk.Frame(temp_card, bg=BG_CARD)
        self.temp_frame.pack(fill="x", padx=14, pady=(0,10))
        self.temp_na_lbl = tk.Label(self.temp_frame,
                                    text="Non disponible sur ce système.",
                                    font=FONT_SMALL, fg=TEXT_MUTED, bg=BG_CARD)
        self.temp_na_lbl.pack(anchor="w")
        self.temp_labels = {}

    # ══════════════════════════════════════════
    #  MISE À JOUR
    # ══════════════════════════════════════════
    def _schedule_update(self):
        self._update()
        self.root.after(1500, self._schedule_update)

    def _launch_timeshift_now(self):
        """Lance le premier refresh Timeshift 3s après le démarrage."""
        if not self._ts_running:
            self._ts_running = True
            threading.Thread(target=self._refresh_timeshift_threaded, daemon=True).start()

    def _update(self):
        now = datetime.now()
        self.lbl_time.config(text=now.strftime("%H:%M:%S  %d/%m/%Y"))
        try:
            up = time.time() - psutil.boot_time()
            self.lbl_uptime.config(text=f"Uptime : {fmt_uptime(up)}")
        except Exception:
            pass

        # ── CPU ──
        cpu_total = psutil.cpu_percent(interval=None)
        cpu_cores = psutil.cpu_percent(interval=None, percpu=True)

        self.ov_cpu_lbl.config(text=f"CPU  {cpu_total:.1f}%")
        self.ov_cpu_bar.set(cpu_total, color_for_pct(cpu_total))
        self.cpu_total_lbl.config(text=f"{cpu_total:.1f}%", fg=color_for_pct(cpu_total))
        self.cpu_total_bar.set(cpu_total, color_for_pct(cpu_total))

        freq = psutil.cpu_freq()
        freq_str = f"{freq.current:.0f} MHz  (min {freq.min:.0f}  max {freq.max:.0f})" if freq else "—"
        self.cpu_info_lbl.config(
            text=f"Modèle : {platform.processor()[:70] or 'N/A'}\n"
                 f"Fréquence : {freq_str}\n"
                 f"Cœurs physiques : {psutil.cpu_count(logical=False)}   "
                 f"Cœurs logiques : {psutil.cpu_count(logical=True)}"
        )
        for i, (bar, lbl) in enumerate(self.core_bars):
            if i < len(cpu_cores):
                v = cpu_cores[i]
                bar.set(v, color_for_pct(v))
                lbl.config(text=f"{v:.0f}%", fg=color_for_pct(v))

        # ── RAM ──
        ram = psutil.virtual_memory()
        self.ov_ram_lbl.config(text=f"RAM  {ram.percent:.1f}%  —  "
                                     f"{fmt_bytes(ram.used)} / {fmt_bytes(ram.total)}")
        self.ov_ram_bar.set(ram.percent, color_for_pct(ram.percent))
        self.ram_big_lbl.config(text=f"{ram.percent:.1f}%  —  {fmt_bytes(ram.used)} utilisés",
                                 fg=color_for_pct(ram.percent))
        self.ram_bar.set(ram.percent, color_for_pct(ram.percent))
        self.ram_detail_lbl.config(
            text=f"Total : {fmt_bytes(ram.total)}   Libre : {fmt_bytes(ram.available)}   "
                 f"Buffers : {fmt_bytes(getattr(ram,'buffers',0))}   "
                 f"Cache : {fmt_bytes(getattr(ram,'cached',0))}"
        )
        swap = psutil.swap_memory()
        self.swap_big_lbl.config(text=f"{swap.percent:.1f}%  —  {fmt_bytes(swap.used)} utilisés",
                                  fg=color_for_pct(swap.percent))
        self.swap_bar.set(swap.percent, color_for_pct(swap.percent))
        self.swap_detail_lbl.config(
            text=f"Total : {fmt_bytes(swap.total)}   Libre : {fmt_bytes(swap.free)}"
        )

        # ── Disques ──
        disk_root = psutil.disk_usage('/')
        self.ov_dsk_lbl.config(text=f"Disque (/)  {disk_root.percent:.1f}%  —  "
                                     f"{fmt_bytes(disk_root.used)} / {fmt_bytes(disk_root.total)}")
        self.ov_dsk_bar.set(disk_root.percent, color_for_pct(disk_root.percent))
        self._refresh_disk_tab()

        # ── Réseau ──
        net_now  = psutil.net_io_counters()
        t_now    = time.time()
        dt       = t_now - self._net_time
        if dt > 0:
            up_speed   = (net_now.bytes_sent - self._net_prev.bytes_sent) / dt
            down_speed = (net_now.bytes_recv - self._net_prev.bytes_recv) / dt
        else:
            up_speed = down_speed = 0
        self._net_prev = net_now
        self._net_time = t_now

        self.ov_net_lbl.config(text=f"↑ {fmt_bytes(up_speed)}/s    ↓ {fmt_bytes(down_speed)}/s")
        self.net_up_lbl.config(text=f"↑  {fmt_bytes(up_speed)}/s")
        self.net_down_lbl.config(text=f"↓  {fmt_bytes(down_speed)}/s")
        self.net_sent_lbl.config(text=f"📤 Envoyé : {fmt_bytes(net_now.bytes_sent)}")
        self.net_recv_lbl.config(text=f"📥 Reçu : {fmt_bytes(net_now.bytes_recv)}")

        # ── Températures ──
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                self.temp_na_lbl.pack_forget()
                for chip, entries in temps.items():
                    for e in entries:
                        key = f"{chip}_{e.label or 'temp'}"
                        color = ACCENT_RED if e.current >= 80 else (ACCENT_ORANGE if e.current >= 65 else ACCENT_GREEN)
                        if key not in self.temp_labels:
                            row = tk.Frame(self.temp_frame, bg=BG_CARD)
                            row.pack(fill="x", pady=1)
                            tk.Label(row, text=f"{chip} / {e.label or '—'}", font=FONT_SMALL,
                                     fg=TEXT_MUTED, bg=BG_CARD, width=30, anchor="w").pack(side="left")
                            lbl = tk.Label(row, text="", font=FONT_VALUE, bg=BG_CARD)
                            lbl.pack(side="left")
                            self.temp_labels[key] = lbl
                        self.temp_labels[key].config(
                            text=f"{e.current:.1f} °C",
                            fg=color
                        )
        except (AttributeError, NotImplementedError):
            pass

# ─────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = DashboardSysteme(root)
    root.mainloop()
