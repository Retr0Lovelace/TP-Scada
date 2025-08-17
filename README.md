README

---
Script.py 

J'ai eu quelque problème à gérer les timings pour pousser les paquets, Désolé 😅

---

Exemple de scénario dangereux :

    - Comportement attendu : quand l’opérateur appuie sur le bouton rouge d’arrêt, le système coupe les tapis et les arrête immédiatement.

    - Comportement malveillant : dans un driver compromis, l’appui sur le bouton rouge n’arrête pas les convoyeurs, mais les accélère volontairement.

Cela expose directement les opérateurs à des risques de projection d’objets, perte de contrôle, blessures graves.

Ici, nous simulons en Python le comportement normal du bouton d'arrêt “safe_driver” et “driver malveillant” qui lui ignore l’arrêt d’urgence et continue à faire tourner un convoyeur.

``` py
#!/usr/bin/env python3

from time import monotonic, sleep
from pyModbusTCP.client import ModbusClient

# -------------------------
# MODBUS SETUP
# -------------------------
HOST, PORT, UNIT_ID = "172.27.160.1", 502, 1

# Boutons (discrete inputs)
IN_BTN_WHITE = 1   # Start
IN_BTN_BLUE  = 2   # Reset total
IN_BTN_BLACK = 3   # Stop process (arrêt d’urgence simulé)

# Actionneurs
CO_ENTRY_CONV = 0
CO_EXIT_CONV  = 2

POLL = 0.1

# -------------------------
# Fonctions utilitaires
# -------------------------
def ensure_open(c: ModbusClient) -> bool:
    if not c.is_open:
        return c.open()
    return True

def r_di(c: ModbusClient, addr: int) -> bool:
    if not ensure_open(c): return False
    v = c.read_discrete_inputs(addr, 1)
    return bool(v and v[0])

def w(c: ModbusClient, addr: int, val: bool):
    if addr is None: return
    if ensure_open(c):
        c.write_single_coil(addr, 1 if val else 0)

# Fonction pour écrire une fréquence simulée sur convoyeur
def set_conveyor_speed(c, speed: float):
    if speed <= 0:
        w(c, CO_ENTRY_CONV, False)
        w(c, CO_EXIT_CONV, False)
        print(f"[SAFE] Convoyeurs arrêtés (speed={speed})")
    else:
        w(c, CO_ENTRY_CONV, True)
        w(c, CO_EXIT_CONV, True)
        print(f"[RUN] Convoyeurs en marche, vitesse = {speed:.1f}x")

# -------------------------
# Drivers
# -------------------------
def safe_driver(c, emergency_stop: bool):
    if emergency_stop:
        set_conveyor_speed(c, 0.0)   # stop total
    else:
        set_conveyor_speed(c, 1.0)   # vitesse normale


def malicious_driver(c, emergency_stop: bool):
    if emergency_stop:
        set_conveyor_speed(c, 50.0)   # accélération dangereuse
        print("Driver malicieux : l’arrêt augmente la vitesse au lieu d’arrêter !!!")
    else:
        set_conveyor_speed(c, 1.0)

# -------------------------
# MAIN DEMO
# -------------------------
def main():
    c = ModbusClient(host=HOST, port=PORT, unit_id=UNIT_ID, auto_open=True, auto_close=True)
    assert ensure_open(c), "Connexion Modbus impossible"

    print("=== Démo driver SÛR ===")
    safe_driver(c, emergency_stop=False)  # marche normale
    sleep(1)
    safe_driver(c, emergency_stop=True)   # doit s'arrêter

    sleep(10)

    print("\n=== Démo driver MALICIEUX ===")
    malicious_driver(c, emergency_stop=False) # marche normale
    sleep(1)
    malicious_driver(c, emergency_stop=True)  # accélère au lieu d’arrêter !

    sleep(30)

    c.close()
    print("\nDéconnexion Modbus.")

if __name__ == "__main__":
    main()
```


Cet exemple nous montre comment un simple changement de comportement d'un équipement dans un driver peut annuler une protection critique physique (arrêt d’urgence) et risqué de blesser un opérateur
