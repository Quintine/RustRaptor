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
 for unit in event.entities { if unit.definition == "iron_coast_stage2_boss_7:unit" { live[unit.entity.to_string()] = true; } }
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
 if event.y < 16 {
  state.units[key] = cursor;
  return #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state};
 }
 let phase = if event.health * 2 <= cursor.max_health { 1 } else { 0 };
 let commands = [#{op:"move",entity:event.entity,x:event.x,y:16}];
 if event.x >= 116 { cursor.direction = -1; }
 if event.x <= 60 { cursor.direction = 1; }
 commands.push(#{op:"velocity",entity:event.entity,vx:cursor.direction,vy:0});
 if phase != cursor.phase {
  cursor.phase = phase;
  cursor.age = 0;
  commands.push(#{op:"animation",entity:event.entity,frame:phase});
  commands.push(#{op:"objective",key:"iron_coast_stage2_boss_7:phase",value:phase+1});
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_7:phase"});
 }
 cursor.age += 1;
 let period = if phase == 0 { 84 } else { 66 };
 let warning = 14;
 if cursor.age % period == period-warning {
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_7:warning"});
  commands.push(#{op:"objective",key:"iron_coast_stage2_boss_7:safe_lane",value:cursor.volley % 2 + 1});
  let side = if cursor.volley % 2 == 0 { 12 } else { 76 };
  commands.push(#{op:"arc",x:event.x+side,y:16+88-10,to_x:event.x+side+24,to_y:16+88-10,ticks:8,anchor:event.entity,to_anchor:event.entity});
 }
 if cursor.age % period == 0 {
  // Fire one broadside at a time. The opposite half remains open.
  let side = if cursor.volley % 2 == 0 { 12 } else { 76 };
  for i in 0..3 {
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_7:shell",x:event.x+side+i*10,y:16+88-8,vx:0,vy:3,hostile:true});
  }
  // Below half health, outward diagonal flank shells still leave the middle
  // and inactive broadside open; no aimed unavoidable point-blank projectile.
  if phase == 1 {
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_7:shell",x:event.x+12,y:16+88-8,vx:-2,vy:3,hostile:true});
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_7:shell",x:event.x+96,y:16+88-8,vx:2,vy:3,hostile:true});
  }
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_7:shot"});
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
 let count = if event.objectives.contains("iron_coast_stage2_boss_7:defeated") { event.objectives["iron_coast_stage2_boss_7:defeated"]+1 } else { 1 };
 #{commands:[#{op:"objective",key:"iron_coast_stage2_boss_7:defeated",value:count},
 #{op:"effect",x:event.x+28,y:event.y+88/2},#{op:"effect",x:event.x+84,y:event.y+88/2},
 #{op:"play_sound",sound:"iron_coast_stage2_boss_7:death"}],state:state}
}
