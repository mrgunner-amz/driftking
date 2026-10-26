(function () {
  'use strict';

  var COLUMNS = 4;
  var KEY = { LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, ENTER: 13, BACK: 10009, ESC: 27 };

  var gridEl = document.getElementById('grid');
  var clockEl = document.getElementById('clock');
  var toastEl = document.getElementById('toast');

  var hasTizen = typeof tizen !== 'undefined' && tizen.application;
  var view = 'home';
  var items = [];
  var focus = 0;
  var toastTimer;

  function toast(message) {
    toastEl.textContent = message;
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, 2500);
  }

  function launch(appId) {
    if (!hasTizen) {
      toast('Not on a TV: would launch ' + appId);
      return;
    }
    try {
      tizen.application.launch(appId, null, function (e) {
        toast('Could not launch: ' + (e && e.message ? e.message : appId));
      });
    } catch (e) {
      toast('Could not launch: ' + e.message);
    }
  }

  function render() {
    gridEl.innerHTML = '';
    gridEl.className = view === 'home' ? 'grid' : 'list';
    items.forEach(function (item, i) {
      var el = document.createElement('div');
      el.setAttribute('role', 'menuitem');
      if (view === 'home') {
        el.className = 'tile' + (item.appId || item.action ? '' : ' unset');
        el.style.setProperty('--accent', item.color || '#444');
        el.textContent = item.name;
      } else {
        el.className = 'row';
        var label = document.createElement('span');
        label.textContent = item.name;
        var id = document.createElement('small');
        id.textContent = item.appId;
        el.appendChild(label);
        el.appendChild(id);
      }
      if (i === focus) el.classList.add('focused');
      gridEl.appendChild(el);
    });
    var focused = gridEl.children[focus];
    if (focused && focused.scrollIntoView) focused.scrollIntoView({ block: 'nearest' });
  }

  function showHome() {
    view = 'home';
    items = window.LAUNCHER_APPS.concat([
      { name: 'Installed apps', action: 'list', color: '#6b7280' }
    ]);
    focus = 0;
    render();
  }

  function showInstalled() {
    if (!hasTizen) {
      toast('Installed apps are only available on the TV');
      return;
    }
    tizen.application.getAppsInfo(function (apps) {
      view = 'apps';
      items = apps
        .map(function (a) { return { name: a.name, appId: a.id }; })
        .sort(function (a, b) { return a.name.localeCompare(b.name); });
      focus = 0;
      render();
    }, function (e) {
      toast('Could not list apps: ' + e.message);
    });
  }

  function activate() {
    var item = items[focus];
    if (!item) return;
    if (item.action === 'list') return showInstalled();
    if (!item.appId) return toast('No app ID set for ' + item.name + ' (edit js/apps.js)');
    launch(item.appId);
  }

  function move(delta) {
    var next = focus + delta;
    if (next < 0 || next >= items.length) return;
    focus = next;
    render();
  }

  function back() {
    if (view !== 'home') return showHome();
    if (hasTizen) tizen.application.getCurrentApplication().exit();
  }

  document.addEventListener('keydown', function (e) {
    var step = view === 'home' ? COLUMNS : 1;
    switch (e.keyCode) {
      case KEY.LEFT:  if (view === 'home') move(-1); break;
      case KEY.RIGHT: if (view === 'home') move(1); break;
      case KEY.UP:    move(-step); break;
      case KEY.DOWN:  move(step); break;
      case KEY.ENTER: activate(); break;
      case KEY.BACK:
      case KEY.ESC:   back(); break;
      default: return;
    }
    e.preventDefault();
  });

  function tickClock() {
    var d = new Date();
    var h = d.getHours() % 12 || 12;
    var m = ('0' + d.getMinutes()).slice(-2);
    clockEl.textContent = h + ':' + m + (d.getHours() < 12 ? ' AM' : ' PM');
  }

  if (typeof tizen !== 'undefined' && tizen.tvinputdevice) {
    try { tizen.tvinputdevice.registerKey('Exit'); } catch (e) { /* not supported */ }
  }

  tickClock();
  setInterval(tickClock, 15000);
  showHome();
})();
