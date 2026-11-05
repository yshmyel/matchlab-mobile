const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');const c=vm.createContext({});vm.runInContext(fs.readFileSync('integrations/MatchLab.gs','utf8'),c);
assert.equal(vm.runInContext("mlUrl_('https://yshmyel.github.io/matchlab-mobile/')",c),'https://yshmyel.github.io/matchlab-mobile/');
assert.throws(()=>vm.runInContext("mlUrl_('https://evil.example/')",c));
assert.equal(vm.runInContext("mlSafe_('=IMPORTDATA(\"secret\")')",c),'\'=IMPORTDATA("secret")');
assert.equal(vm.runInContext('mlSafe_(0)',c),0);
const row=vm.runInContext("mlResearchRows_({updated_utc:'now',predictions:[{key:'k',league:'nba',player:'X',market:'nplus',threshold:6,stat:'rebounds',selection:'hit',probability:.5,grade:'Loss',actual:0,actual_value:0}]})[0]",c);assert.equal(row.length,14);assert.equal(row[9],0);
console.log('PASS: private sheet sync host guard, formula injection guard, zero results and schema');
