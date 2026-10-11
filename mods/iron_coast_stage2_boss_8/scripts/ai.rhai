// Per-entity cursors prevent simultaneous carriers sharing phase/volley state.
fn alive(event) {
 for unit in event.entities { if unit.entity == event.entity && unit.health > 0 { return true; } }
 false
}
fn on_spawn(event,state,random) {
 // A new spawn is a fresh lifecycle even when killed before dispatch.
 if state.contains("last_death") && state.last_death == event.entity { state.remove("last_death"); }
 if !alive(event) { return #{commands:[],state:state}; }
 if !state.contains("units") { state.units = #{}; }
 // Prune cursors from aborted/restarted worlds; retain simultaneous live carriers.
 let live = #{};
 for unit in event.entities { if unit.definition == "iron_coast_stage2_boss_8:unit" { live[unit.entity.to_string()] = true; } }
 for old in state.units.keys() { if !live.contains(old) { state.units.remove(old); } }
 let spawn_health = 1;
 for unit in event.entities { if unit.entity == event.entity { spawn_health = unit.health; } }
 state.units[event.entity.to_string()] = #{age:0,volley:0,direction:1,phase:0,max_health:spawn_health};
 #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2},#{op:"animation",entity:event.entity,frame:0}],state:state}
}
fn on_tick(event,state,random) {
 if event.health <= 0 || !alive(event) { return #{commands:[],state:state}; }
 let key = event.entity.to_string();
 if !state.contains("units") { state.units = #{}; }
 let cursor = if state.units.contains(key) { state.units[key] } else { #{age:0,volley:0,direction:1,phase:0,max_health:event.health} };
 if event.y < 4 {
  state.units[key] = cursor;
  return #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state};
 }
 let phase = if event.health * 3 <= cursor.max_health { 2 } else if event.health * 3 <= cursor.max_health * 2 { 1 } else { 0 };
 let commands = [#{op:"move",entity:event.entity,x:event.x,y:4}];
 if event.x >= 116 { cursor.direction = -1; }
 if event.x <= 60 { cursor.direction = 1; }
 commands.push(#{op:"velocity",entity:event.entity,vx:cursor.direction,vy:0});
 if phase != cursor.phase {
  cursor.phase = phase;
  cursor.age = 0;
  commands.push(#{op:"animation",entity:event.entity,frame:phase});
  commands.push(#{op:"objective",key:"iron_coast_stage2_boss_8:phase",value:phase+1});
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_8:phase"});
 }
 cursor.age += 1;
 let period = if phase == 0 { 96 } else if phase == 1 { 84 } else { 72 };
 let warning = 18;
 if cursor.age % period == period-warning {
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_8:warning"});
  commands.push(#{op:"objective",key:"iron_coast_stage2_boss_8:safe_lane",value:cursor.volley % 3 + 1});
  // Blue charge arcs indicate the attacking pods, not an explosion.
  let safe = cursor.volley % 3;
  for lane in 0..3 {
   if lane != safe {
    commands.push(#{op:"arc",x:event.x+12+lane*32,y:4+112-14,to_x:event.x+28+lane*32,to_y:4+112-14,ticks:8,anchor:event.entity,to_anchor:event.entity});
   }
  }
 }
 if cursor.age % period == 0 {
  let safe = cursor.volley % 3;
  if phase == 0 {
   // Wide outward fan leaves the central column entirely open.
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_8:shell",x:event.x+16,y:4+112-12,vx:-2,vy:3,hostile:true});
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_8:shell",x:event.x+32,y:4+112-12,vx:-1,vy:3,hostile:true});
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_8:shell",x:event.x+76,y:4+112-12,vx:1,vy:3,hostile:true});
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_8:shell",x:event.x+92,y:4+112-12,vx:2,vy:3,hostile:true});
  } else {
   // Every later volley leaves one full32px deck lane open; the warning names
   // it eighteen ticks early. Phase3 adds only outward flank shots.
   for lane in 0..3 {
    if lane != safe {
     for i in 0..2 { commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_8:shell",x:event.x+12+lane*32+i*10,y:4+112-12,vx:0,vy:3,hostile:true}); }
    }
   }
   if phase == 2 {
    commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_8:shell",x:event.x+8,y:4+112-12,vx:-2,vy:3,hostile:true});
    commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_8:shell",x:event.x+100,y:4+112-12,vx:2,vy:3,hostile:true});
   }
  }
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_8:shot"});
  cursor.volley += 1;
 }
 state.units[key] = cursor;
 #{commands:commands,state:state}
}
fn on_hit(event,state,random) { #{commands:[],state:state} }
fn on_death(event,state,random) {
 if state.contains("last_death") && state.last_death == event.entity { return #{commands:[],state:state}; }
 state.last_death = event.entity;
 if state.contains("units") { state.units.remove(event.entity.to_string()); }
 let count = if event.objectives.contains("iron_coast_stage2_boss_8:defeated") { event.objectives["iron_coast_stage2_boss_8:defeated"]+1 } else { 1 };
 #{commands:[#{op:"objective",key:"iron_coast_stage2_boss_8:defeated",value:count},
 #{op:"effect",x:event.x+28,y:event.y+112/2},#{op:"effect",x:event.x+84,y:event.y+112/2},
 #{op:"play_sound",sound:"iron_coast_stage2_boss_8:death"}],state:state}
}
