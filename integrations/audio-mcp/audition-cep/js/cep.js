(function () {
  "use strict";

  window.AudioMcpCep = {
    userDataPath: function () {
      return window.__adobe_cep__.getSystemPath("userData");
    },
    readFile: function (path) {
      return window.cep.fs.readFile(path);
    }
  };
}());
