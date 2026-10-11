// Deterministic per-entity patrol, health phases and visible/audio warning windows.
fn alive(event) { for unit in event.entities { if unit.entity==event.entity && unit.health>0 { return true; } } false }
fn spawn_health(event) { for unit in event.entities { if unit.entity==event.entity {return unit.health.max(1);} } 1 }
// At most128 retired IDs survive checkpoint/replay. Upgrade older checkpoints
// without a FIFO by retaining a deterministic bounded subset of their guards.
fn ready(state) {
 if !state.contains("units") {state.units=#{};}
 if !state.contains("dead") {state.dead=#{};}
 if !state.contains("dead_order") {
  let retained=#{};let order=[];
  for key in state.dead.keys() {
   if order.len()>=128 {let oldest=order.remove(0);retained.remove(oldest);}
   retained[key]=true;order.push(key);
  }
  state.dead=retained;state.dead_order=order;
 }
 state
}
fn on_spawn(event,state,random) {
 state=ready(state);
 // Discard clocks of entities absent from this World after an abandoned run.
 // Existing live peers retain their independent clocks.
 let live_units=#{};
 for unit in event.entities {
  let unit_key=unit.entity.to_string();
  if unit.health>0 && state.units.contains(unit_key) {live_units[unit_key]=state.units[unit_key];}
 }
 state.units=live_units;
 let key=event.entity.to_string();state.dead.remove(key);state.units.remove(key);
 let keep=[];for old in state.dead_order {if old!=key {keep.push(old);}}state.dead_order=keep;
 // A lethal spawn-step collision still clears this lifecycle's old death flag.
 if !alive(event) {return #{commands:[],state:state};}
 state.units[key]=#{age:0,direction:1,aim:0,phase:1,max_health:spawn_health(event)};
 #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state}
}
fn on_tick(event,state,random) {
 if event.health<=0 || !alive(event) {return #{commands:[],state:state};}
 if !state.contains("units") {state.units=#{};}
 let key=event.entity.to_string();
 if !state.units.contains(key) {state.units[key]=#{age:0,direction:1,aim:0,phase:1,max_health:spawn_health(event)};}
 if event.y<24 {return #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state};}
 let u=state.units[key];
 if !u.contains("max_health") {u.max_health=spawn_health(event);}
 if event.x>=148 {u.direction=-1;} if event.x<=68 {u.direction=1;}
 let phase=if event.health>u.max_health/2 {1} else {2};
 // Each new phase begins a complete warning window, independent of the old
 // period. This also safely upgrades checkpoints lacking the phase latch.
 if !u.contains("phase") {u.phase=1;}
 if phase!=u.phase {u.phase=phase;u.age=0;}
 let period=if phase==1 {76} else {64};
 let cycle=u.age%period;
 let commands=[#{op:"move",entity:event.entity,x:event.x,y:24},#{op:"velocity",entity:event.entity,vx:if cycle<14 {0} else {u.direction*2},vy:0}];
 if cycle==0 {
  u.aim=if event.player_x<event.x+52 {-1} else {1};
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_4:warning"});
  commands.push(#{op:"objective",key:"iron_coast_stage2_boss_4:phase",value:phase});
  commands.push(#{op:"arc",x:event.x+20,y:76,to_x:event.x+20,to_y:94,ticks:8});
  commands.push(#{op:"arc",x:event.x+84,y:76,to_x:event.x+84,to_y:94,ticks:8});
 }
 if cycle==14 {
  commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_4:shell",x:event.x+20,y:78,vx:-1,vy:4,hostile:true});
  commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_4:shell",x:event.x+84,y:78,vx:1,vy:4,hostile:true});
  if phase==2 {
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_4:shell",x:event.x+40,y:78,vx:-1,vy:4,hostile:true});
   commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_4:shell",x:event.x+64,y:78,vx:1,vy:4,hostile:true});
  }
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_4:shot"});
 }
 u.age+=1;state.units[key]=u;
 #{commands:commands,state:state}
}
fn on_death(event,state,random) {
 state=ready(state);
 let key=event.entity.to_string();if state.dead.contains(key) {return #{commands:[],state:state};}
 if state.dead_order.len()>=128 {let oldest=state.dead_order.remove(0);state.dead.remove(oldest);}
 state.dead[key]=true;state.dead_order.push(key);state.units.remove(key);
 let count=if event.objectives.contains("iron_coast_stage2_boss_4:defeated") {event.objectives["iron_coast_stage2_boss_4:defeated"]+1} else {1};
 #{commands:[#{op:"objective",key:"iron_coast_stage2_boss_4:defeated",value:count},#{op:"effect",x:event.x+20,y:event.y+40},#{op:"effect",x:event.x+84,y:event.y+40},#{op:"play_sound",sound:"iron_coast_stage2_boss_4:death"}],state:state}
}
