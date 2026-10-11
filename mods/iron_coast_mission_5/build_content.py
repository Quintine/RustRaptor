#!/usr/bin/env python3
"""Emit the version 1 mission content definitions from a small auditable schedule."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAMESPACE = "iron_coast_mission_5"


def art(name, width, height):
    return {"png":f"art/{name}_sd.png","hd_png":f"art/{name}_hd.png",
            "logical_width":width,"logical_height":height,"frames":1}


spawns = []
# Fast escorts cover both flanks; gaps between formations leave time to acquire
# the foundry targets. No ordinary escort or terrain turret is mandatory.
for start, positions in [(50,[56,216,136]),(360,[80,200,136]),
                         (620,[56,216,136]),(1040,[80,200,136]),
                         (1300,[56,216,136]),(1500,[80,200,136])]:
    for index,x in enumerate(positions):
        spawns.append({"tick":start+index*38,"enemy":"iron_coast_scout:unit","x":x,"y":-24})
# Reference original content directly: native art, collision, firing, reward,
# bank animation and movement path all remain owned by the base registry.
for index,enemy,x in [(0,"base:enemy_0_22",40),(1,"base:enemy_0_21",208),
                      (3,"base:enemy_1_26",64),(4,"base:enemy_1_25",208),
                      (6,"base:enemy_0_13",72),(9,"base:enemy_0_8",216)]:
    spawns[index]["enemy"] = enemy
    spawns[index]["x"] = x
for tick,x in [(180,40),(500,232),(810,40),(1210,232)]:
    spawns.append({"tick":tick,"enemy":"iron_coast_turret:unit","x":x,"y":-32})
for tick,x in [(240,112),(920,176)]:
    spawns.append({"tick":tick,"enemy":f"{NAMESPACE}:foundry","x":x,"y":-48})
spawns.append({"tick":1660,"enemy":"iron_coast_boss_5:unit","x":112,"y":24})
spawns.sort(key=lambda s:s["tick"])

sound_names = {
    "approach":"Cinder Docks approach",
    "foundry_alarm":"Armored foundry online",
    "heat_warning":"Slag lane warning",
    "slag_release":"Industrial slag release",
    "foundry_shot":"Foundry defense cannon",
    "foundry_shutdown":"Foundry shutdown",
    "launch_alarm":"Launch cruiser alarm",
    "coolant_use":"Coolant injector",
    "victory":"Cinder Docks shutdown confirmed"
}

pack = {
    "weapons":[{
        "id":f"{NAMESPACE}:slag","name":"Cinder Slag Shell","damage":4,
        "speed":5,"cooldown":150,"behavior":"straight","target":"all",
        "art":art("slag",8,8)
    }],
    "items":[{
        "id":f"{NAMESPACE}:coolant","name":"Foundry Coolant Injector",
        "price":15000,"max_count":5,"initial_count":1,"special":True,
        "consumable":True,"art":art("coolant",16,16),"script":"scripts/coolant.rhai",
        "description":"Selectable consumable. Press Special to restore 30 energy, consuming one injector. Carry up to five. Priced at 500 credits per shield unit, matching Iron Coast field repairs."
    }],
    "enemies":[{
        "id":f"{NAMESPACE}:foundry","name":"Armored Furnace Station",
        "health":90,"speed":0,"reward":1200,"ground":True,"boss":False,
        "cooldown":150,"weapon":f"{NAMESPACE}:slag",
        "art":art("foundry",48,48),"script":"scripts/foundry.rhai"
    }],
    "sounds":[{
        "id":f"{NAMESPACE}:{key}","name":name,"file":f"audio/{key}.wav",
        "volume":100 if key not in ["victory","launch_alarm"] else 115,
        "pan":127,"pitch":128,"priority":3 if key in ["heat_warning","launch_alarm","victory"] else 2
    } for key,name in sound_names.items()],
    "missions":[{
        "id":f"{NAMESPACE}:mission_05","name":"Iron Coast 5 — Cinder Docks",
        "duration":2600,"auto_complete":False,"columns":9,
        "music_track":"iron_coast_music:iron_coast",
        "layout":list(range(216))*4,
        "tiles":[{"art":art(f"tile_{n:03}",32,32)} for n in range(216)],
        "spawns":spawns,"art":art("briefing",320,200),"script":"scripts/mission.rhai"
    }]
}
(ROOT/"content.json").write_text(json.dumps(pack,indent=2)+"\n")
print(f"Emitted {len(spawns)} scheduled enemies and {len(pack['missions'][0]['tiles'])} terrain tiles")
