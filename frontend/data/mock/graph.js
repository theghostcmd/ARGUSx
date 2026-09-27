export const graph={nodes:[
{id:'USER-17',label:'USER-17',type:'user',risk:'critical',detail:'Privileged operator account'},
{id:'DEVICE-42',label:'DEVICE-42',type:'device',risk:'critical',detail:'Engineering workstation'},
{id:'OT-NET',label:'OT-NET',type:'network',risk:'high',detail:'Operational technology segment'},
{id:'PLC-07',label:'PLC-07',type:'device',risk:'medium',detail:'Line controller'},
{id:'API-GW',label:'API-GW',type:'service',risk:'medium',detail:'Internal service gateway'},
{id:'PROD-DB-01',label:'PROD-DB-01',type:'database',risk:'critical',detail:'Production telemetry database'},
{id:'USER-08',label:'USER-08',type:'user',risk:'medium',detail:'Engineering analyst'},
{id:'DEVICE-11',label:'DEVICE-11',type:'device',risk:'high',detail:'Engineering workstation'}],edges:[
['USER-17','DEVICE-42'],['DEVICE-42','OT-NET'],['OT-NET','PLC-07'],['DEVICE-42','API-GW'],['API-GW','PROD-DB-01'],['USER-08','DEVICE-11'],['DEVICE-11','OT-NET']]}
