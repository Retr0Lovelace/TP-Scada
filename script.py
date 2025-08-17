#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from time import monotonic, sleep
import heapq
from pyModbusTCP.client import ModbusClient

# -------------------------
# MODBUS (confirmé)
# -------------------------
HOST, PORT, UNIT_ID = "172.27.160.1", 502, 1

# Boutons (discrete inputs)
IN_BTN_WHITE = 1   # Start
IN_BTN_BLUE  = 2   # Reset total
IN_BTN_BLACK = 3   # Stop process

# Vision sensor (✱ confirmé sur Input Register 0)
IR_VISION = 0

# Actionneurs (confirmés par tes tests)
CO_ENTRY_CONV = 0
CO_EXIT_CONV  = 2
CO_S1_TURN, CO_S1_BELT = 3, 4     # BLEU  -> Sorter 1 (slot proche)
CO_S2_TURN, CO_S2_BELT = 5, 6     # VERT  -> Sorter 2 (2e slot)
CO_L_START, CO_L_RESET, CO_L_STOP = 9, 10, 11
CO_EMITTER = 12

# Optionnels (renseigne si mappés dans FIO)
CO_FIO_RUN   = None
CO_FIO_RESET = None

# -------------------------
# PARAMÈTRES
# -------------------------
POLL = 0.01

# Test rapide : pousser immédiatement quand la couleur est détectée
# (met à True pour vérifier bout-en-bout détection -> mouvement)
IMMEDIATE_PUSH = False

# Temps de trajet depuis la caméra jusqu’au point de tir
T_TO_S1 = 0.35   # BLEU  -> Sorter 1 (slot proche)
T_TO_S2 = 0.80   # VERT  -> Sorter 2

# Durée de poussée (TURN + BELT ON)
PUSH_S1 = 0.50
PUSH_S2 = 0.50

BLUE, GREEN, METAL = {1,2,3}, {4,5,6}, {7,8,9}

# -------------------------
# UTILS MODBUS
# -------------------------
def ensure_open(c: ModbusClient) -> bool:
    if not c.is_open:
        return c.open()
    return True

def r_di(c: ModbusClient, addr: int) -> bool:
    if not ensure_open(c): return False
    v = c.read_discrete_inputs(addr, 1)
    return bool(v and v[0])

def r_ir(c: ModbusClient, addr: int) -> int:
    if not ensure_open(c): return 0
    v = c.read_input_registers(addr, 1)
    return int(v[0]) if v else 0

def w(c: ModbusClient, addr: int | None, val: bool):
    if addr is None: return
    if ensure_open(c):
        c.write_single_coil(addr, 1 if val else 0)

# -------------------------
# ACTIONS
# -------------------------
def conveyors_on(c):  w(c, CO_ENTRY_CONV, True);  w(c, CO_EXIT_CONV, True)
def conveyors_off(c): w(c, CO_ENTRY_CONV, False); w(c, CO_EXIT_CONV, False)
def emitter_on(c):    w(c, CO_EMITTER, True)
def emitter_off(c):   w(c, CO_EMITTER, False)
def fio_run_on(c):    w(c, CO_FIO_RUN, True)
def fio_run_off(c):   w(c, CO_FIO_RUN, False)
def fio_reset(c, dur=0.6):
    if CO_FIO_RESET is None: return
    w(c, CO_FIO_RESET, True); t = monotonic() + dur
    while monotonic() < t: sleep(POLL)
    w(c, CO_FIO_RESET, False)
def lights(c, start=False, stop=False, reset=False):
    w(c, CO_L_START, start); w(c, CO_L_STOP, stop); w(c, CO_L_RESET, reset)

def s1_on(c):  w(c, CO_S1_TURN, True); w(c, CO_S1_BELT, True)
def s1_off(c): w(c, CO_S1_BELT, False); w(c, CO_S1_TURN, False)
def s2_on(c):  w(c, CO_S2_TURN, True); w(c, CO_S2_BELT, True)
def s2_off(c): w(c, CO_S2_BELT, False); w(c, CO_S2_TURN, False)

def process_start(c):
    fio_run_on(c)
    conveyors_on(c); emitter_on(c)
    s1_off(c); s2_off(c)
    lights(c, start=True, stop=False, reset=False)

def process_stop_only(c):
    emitter_off(c); conveyors_off(c); s1_off(c); s2_off(c)
    lights(c, start=False, stop=True, reset=False)

def process_stop_all_and_reset(c):
    emitter_off(c); conveyors_off(c); s1_off(c); s2_off(c)
    fio_run_off(c); lights(c, start=False, stop=False, reset=True); fio_reset(c)

# -------------------------
# TRI
# -------------------------
def classify(code: int) -> str | None:
    if code in BLUE:  return "BLUE"
    if code in GREEN: return "GREEN"
    if code in METAL: return "METAL"
    return None

_seq = 0
def schedule(heap, when, kind: str):
    global _seq; _seq += 1
    heapq.heappush(heap, (when, _seq, kind))

# -------------------------
# MAIN
# -------------------------
def main():
    c = ModbusClient(host=HOST, port=PORT, unit_id=UNIT_ID, auto_open=True, auto_close=True)
    while not ensure_open(c):
        print("Connexion Modbus…"); sleep(0.3)
    print("Connecté. Vision sur IR0 confirmé.")

    lights(c, False, False, False); s1_off(c); s2_off(c)

    last_white = last_black = last_blue = False
    last_code = 0
    running = False
    events = []

    try:
        while True:
            if not ensure_open(c): sleep(0.2); continue

            # --- Boutons ---
            white = r_di(c, IN_BTN_WHITE)
            black = r_di(c, IN_BTN_BLACK)
            blue  = r_di(c, IN_BTN_BLUE)

            if white and not last_white:
                print("[BLANC] Start (tapis + émetteur)")
                process_start(c); running = True; events.clear()

            if black and not last_black:
                print("[NOIR] Stop (tapis + émetteur)")
                process_stop_only(c); running = False; events.clear()

            if blue and not last_blue:
                print("[BLEU] Stop + Reset")
                process_stop_all_and_reset(c); running = False; events.clear()

            last_white, last_black, last_blue = white, black, blue

            # --- Vision ---
            code = r_ir(c, IR_VISION)
            if code != last_code:
                print(f"[VISION] IR0={code} -> {classify(code) or '-'}")
                last_code = code

                # détection d'une nouvelle pièce ?
                if running and code in (1,2,3,4,5,6,7,8,9):
                    color = classify(code)
                    now = monotonic()
                    if IMMEDIATE_PUSH:
                        # Mode test: pousse tout de suite pour valider la chaîne complète
                        if color == "BLUE":
                            print("TEST: push immédiat S1")
                            s1_on(c); t = monotonic() + PUSH_S1
                            while monotonic() < t: sleep(POLL)
                            s1_off(c)
                        elif color == "GREEN":
                            print("TEST: push immédiat S2")
                            s2_on(c); t = monotonic() + PUSH_S2
                            while monotonic() < t: sleep(POLL)
                            s2_off(c)
                    else:
                        # Mode normal: planifier selon les temps de trajet
                        if color == "BLUE":
                            t = now + T_TO_S1
                            schedule(events, t,           "S1_ON")
                            schedule(events, t + PUSH_S1, "S1_OFF")
                            print(f"→ BLEU : S1 @ +{T_TO_S1:.2f}s (push {PUSH_S1:.2f}s)")
                        elif color == "GREEN":
                            t = now + T_TO_S2
                            schedule(events, t,           "S2_ON")
                            schedule(events, t + PUSH_S2, "S2_OFF")
                            print(f"→ VERT : S2 @ +{T_TO_S2:.2f}s (push {PUSH_S2:.2f}s)")
                        else:
                            # METAL : laisser filer
                            print("→ METAL : tout droit")

            # --- Exécution des événements planifiés ---
            now = monotonic()
            while events and events[0][0] <= now:
                _, _, kind = heapq.heappop(events)
                if   kind == "S1_ON":  s1_on(c)
                elif kind == "S1_OFF": s1_off(c)
                elif kind == "S2_ON":  s2_on(c)
                elif kind == "S2_OFF": s2_off(c)

            sleep(POLL)

    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        events.clear(); s1_off(c); s2_off(c)
        process_stop_only(c)
        c.close(); print("Déconnecté proprement.")

if __name__ == "__main__":
    main()
