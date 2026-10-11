// Retain at most128 recently retired entity IDs. Older checkpoints lacking
// the FIFO migrate deterministically before any new spawn/death is processed.
fn ready(state) {
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
fn live(event) {for e in event.entities {if e.entity==event.entity && e.health>0 {return true;}}false}
fn on_spawn(event,state,random) {
 state=ready(state);
 let key=event.entity.to_string();state.dead.remove(key);
 let keep=[];for old in state.dead_order {if old!=key {keep.push(old);}}state.dead_order=keep;
 #{commands:[],state:state}
}
fn on_tick(event,state,random) {
 if event.health<=0 || !live(event) {return #{commands:[],state:state};}
 // Ground scroll is rebased every tick after arrival so a mandatory survivor
 // remains reachable indefinitely. No target escapes or disappears on a timer.
 if event.y>=60 {return #{commands:[#{op:"move",entity:event.entity,x:event.x,y:60},#{op:"velocity",entity:event.entity,vx:0,vy:0}],state:state};}
 #{commands:[],state:state}
}
fn on_death(event,state,random) {
 state=ready(state);
 let key=event.entity.to_string();if state.dead.contains(key) {return #{commands:[],state:state};}
 if state.dead_order.len()>=128 {let oldest=state.dead_order.remove(0);state.dead.remove(oldest);}
 state.dead[key]=true;state.dead_order.push(key);
 let count=if event.objectives.contains("iron_coast_stage2_mission_4:targets_destroyed") {event.objectives["iron_coast_stage2_mission_4:targets_destroyed"]+1} else {1};
 #{commands:[#{op:"objective",key:"iron_coast_stage2_mission_4:targets_destroyed",value:count},#{op:"shield",amount:12},#{op:"play_sound",sound:"iron_coast_stage2_mission_4:salvage"}],state:state}
}
