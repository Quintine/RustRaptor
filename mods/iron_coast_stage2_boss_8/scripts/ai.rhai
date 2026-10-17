// Private Stage2 retune. Content IDs, health/rewards/art canvases and death objective stay stable.
// Difficulty is optional until the small general event API is actually applied; v1 falls back to1.
fn level(event) { if event.contains("difficulty") {event.difficulty.max(0).min(3)} else {1} }
// Queued hook-local health/x/y may predate preceding callbacks. Use the live actor.
// A present null actor is retired/nonenemy and MUST NOT fall back to the older entity list.
fn current(event) {
 let actor=#{};
 if event.contains("actor") {if event.actor!=() {actor=event.actor;}}
 else {for e in event.entities {if e.entity==event.entity {actor=e;break;}}}
 event.live=false;
 if actor.contains("health") {event.health=actor.health;event.x=actor.x;event.y=actor.y;event.live=actor.health>0;}
 else {event.health=0;}
 if event.contains("player") && event.player.contains("x") {event.player_x=event.player.x;}
 event
}
fn alive(event) {event.live}
fn maximum(event) {event.health.max(1)}
fn ready(state) {
 if !state.contains("units") {state.units=#{};}
 // Migrate original Gatebreaker/Undertow map cursors once. Start a full new warning window.
 if state.contains("ages") {
  for key in state.ages.keys() {
   if !state.units.contains(key) {
    let hp=if state.contains("maximums") && state.maximums.contains(key) {state.maximums[key]} else {1};
    let dir=if state.contains("directions") && state.directions.contains(key) {state.directions[key]} else {1};
    state.units[key]=#{max_health:hp,direction:dir,volley:0};
   }
  }
  state.remove("ages");state.remove("phases");state.remove("directions");state.remove("maximums");
 }
 if !state.contains("dead") {state.dead=#{};}
 if !state.contains("dead_order") {
  let order=[];let kept=#{};
  for key in state.dead.keys() {if order.len()>=128 {let old=order.remove(0);kept.remove(old);} kept[key]=true;order.push(key);}
  state.dead=kept;state.dead_order=order;
 }
 // Old carrier last_death is also retained as a bounded duplicate-death guard.
 if state.contains("last_death") {
  let key=state.last_death.to_string();
  if !state.dead.contains(key) {
   if state.dead_order.len()>=128 {let old=state.dead_order.remove(0);state.dead.remove(old);}
   state.dead[key]=true;state.dead_order.push(key);
  }
  state.remove("last_death");
 }
 state
}
fn upgrade(u,event) {
 if !u.contains("schema") || u.schema!=2 {
  let hp=if u.contains("max_health") {u.max_health.max(event.health).max(1)} else {maximum(event)};
  let dir=if u.contains("direction") {u.direction} else {1};
  let volley=if u.contains("volley") {u.volley.max(0)} else {0};
  u=#{schema:2,age:0,phase:0,max_health:hp,direction:dir,volley:volley,aim:0,anchor_x:event.x};
 }
 u
}
fn shot(commands,weapon,x,y,vx,vy) {commands.push(#{op:"projectile",weapon:weapon,x:x,y:y,vx:vx,vy:vy,hostile:true});commands}
fn charge(commands,event,x,y) {
 commands.push(#{op:"arc",x:x,y:y,to_x:x+12,to_y:y,ticks:8,anchor:event.entity,to_anchor:event.entity});commands
}
fn aim_charge(commands,event,x,y,vx,vy) {
 commands.push(#{op:"arc",x:x,y:y,to_x:x+vx*4,to_y:y+vy*4,ticks:8,anchor:event.entity,to_anchor:event.entity});commands
}
fn on_spawn(event,state,random) {
 event=current(event);state=ready(state);let key=event.entity.to_string();
 let live=#{};
 for e in event.entities {let k=e.entity.to_string();if e.health>0 && e.definition=="iron_coast_stage2_boss_8:unit" && state.units.contains(k) {live[k]=state.units[k];}}
 state.units=live;state.dead.remove(key);
 let keep=[];for old in state.dead_order {if old!=key {keep.push(old);}}state.dead_order=keep;
 if !alive(event) {return #{commands:[],state:state};}
 state.units[key]=upgrade(#{max_health:maximum(event),direction:1,volley:0},event);
 let commands=[#{op:"velocity",entity:event.entity,vx:0,vy:2}];
 commands.push(#{op:"animation",entity:event.entity,frame:0});
 #{commands:commands,state:state}
}
fn on_tick(event,state,random) {
 event=current(event);if event.health<=0 || !alive(event) {return #{commands:[],state:state};}
 state=ready(state);let key=event.entity.to_string();
 let u=upgrade(if state.units.contains(key) {state.units[key]} else {#{}},event);
 if event.y<4 {state.units[key]=u;return #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state};}
 let phase=if event.health*3<=u.max_health {3} else if event.health*3<=u.max_health*2 {2} else {1};
 let commands=[];
 if phase!=u.phase {
  u.phase=phase;u.age=0;
  commands.push(#{op:"objective",key:"iron_coast_stage2_boss_8:phase",value:phase});
  commands.push(#{op:"animation",entity:event.entity,frame:phase-1});
 }
 let d=level(event);u.difficulty=d;let periods=[[140,126,112,100],[126,112,100,90],[114,102,90,80]];let warning=[32,30,28,26][d];let period=periods[phase-1][d];let cycle=u.age%period;
 let x=event.x.max(60).min(116);let y=4;
 // Track only before charge; aim and deck position are frozen throughout the attack window.
 if cycle==0 {u.anchor_x=x;u.aim=((event.player_x+16)-(x+56))/40;u.aim=u.aim.max(-2).min(2);}
 let locked=cycle<=warning;
 if locked {x=u.anchor_x;}
 let goal=if u.volley%2==0 {60} else {116};let vx=if locked || (goal-x).abs()<=2 {0} else if goal<x {-1} else {1};
 commands.push(#{op:"move",entity:event.entity,x:x,y:y});
 commands.push(#{op:"velocity",entity:event.entity,vx:vx,vy:0});
 if cycle==0 {
  commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_8:warning"});
  commands.push(#{op:"objective",key:"iron_coast_stage2_boss_8:safe_lane",value:if phase==1 {2} else {u.volley%3+1}});
 }
 if cycle<warning && cycle%8==0 {
  let safe=u.volley%3;if phase==1 {commands=charge(commands,event,x+12,y+100);commands=charge(commands,event,x+88,y+100);} else {for lane in 0..3 {if lane!=safe {commands=charge(commands,event,x+12+lane*32,y+100);}}if phase==3 {commands=aim_charge(commands,event,x+8,y+100,-2,3);commands=aim_charge(commands,event,x+100,y+100,2,3);}}
 }
 if cycle==warning {let safe=u.volley%3;if phase==1 {commands=shot(commands,"iron_coast_stage2_boss_8:shell",x+16,y+100,-2,3);commands=shot(commands,"iron_coast_stage2_boss_8:shell",x+32,y+100,-1,3);commands=shot(commands,"iron_coast_stage2_boss_8:shell",x+76,y+100,1,3);commands=shot(commands,"iron_coast_stage2_boss_8:shell",x+92,y+100,2,3);} else {let count=if d==0 {1} else {2};for lane in 0..3 {if lane!=safe {for i in 0..count {commands=shot(commands,"iron_coast_stage2_boss_8:shell",x+12+lane*32+i*10,y+100,0,3);}}}if phase==3 {commands=shot(commands,"iron_coast_stage2_boss_8:shell",x+8,y+100,-2,3);commands=shot(commands,"iron_coast_stage2_boss_8:shell",x+100,y+100,2,3);}}commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_8:shot"});}
 u.age+=1;
 if cycle==warning {u.volley+=1;}
 state.units[key]=u;
 #{commands:commands,state:state}
}
fn on_hit(event,state,random) {#{commands:[],state:state}}
fn on_death(event,state,random) {
 event=current(event);state=ready(state);let key=event.entity.to_string();
 if alive(event) || state.dead.contains(key) {return #{commands:[],state:state};}
 if state.dead_order.len()>=128 {let old=state.dead_order.remove(0);state.dead.remove(old);}
 state.dead[key]=true;state.dead_order.push(key);state.units.remove(key);
 let count=if event.objectives.contains("iron_coast_stage2_boss_8:defeated") {event.objectives["iron_coast_stage2_boss_8:defeated"]+1} else {1};
 #{commands:[#{op:"objective",key:"iron_coast_stage2_boss_8:defeated",value:count},#{op:"effect",x:event.x+28,y:event.y+56},#{op:"effect",x:event.x+84,y:event.y+56},#{op:"play_sound",sound:"iron_coast_stage2_boss_8:death"}],state:state}
}
