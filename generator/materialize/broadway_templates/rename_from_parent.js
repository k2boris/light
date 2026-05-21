self.result = [];

var s = "";
if (inputs !== null && inputs !== undefined) {
  s = "" + inputs;
}

s = s.trim().replace(/^\[/, "").replace(/\]$/, "");

if (s) {
  var parts = s.split(",");
  for (var i = 0; i < parts.length; i++) {
    var v = parts[i].trim().replace(/^\[/, "").replace(/\]$/, "");
    if (v) self.result.push({ {{rename_alias}}: v });
  }
}

self.result;
