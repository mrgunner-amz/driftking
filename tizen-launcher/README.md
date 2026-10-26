# Clear Launcher

A small Samsung Tizen TV web app: a grid of tiles for the apps you actually
use, plus a clock. It runs next to Samsung's home screen, not instead of it.

This is independent of the rest of the DriftKing repository.

## Run on a TV

1. On the TV: Smart Hub > Apps > App Settings, type `12345`, set Developer
   mode to On, enter your computer's IP address, then reboot the TV.
2. In Tizen Studio: Tools > Device Manager > Remote Device Manager > `+`, then
   add the TV's name, IP address and port.
3. Import this folder as a Tizen web project and run it on the TV.

Steps are from the
[Samsung TV device guide](https://developer.samsung.com/smarttv/develop/getting-started/using-sdk/tv-device.html).
Running on a real TV also needs a Samsung developer certificate set up in
Tizen Studio.

## Try it in a desktop browser

Open `index.html` directly. Arrow keys move, Enter opens, Esc goes back.
Launching shows a message instead of opening an app, since there is no
`tizen` API outside the TV.

## Customise

- Tiles live in `js/apps.js`. A tile with an empty `appId` is dimmed.
- The default app IDs are commonly cited values and may not match your TV's
  model year or region. Open the **Installed apps** tile on the TV to see the
  real IDs, then copy them into `js/apps.js`.
- Selecting an app in the **Installed apps** list launches it, which is a
  quick way to test an ID.

## Not yet verified on hardware

Only the desktop-browser behaviour has been tested. Launching apps and
listing installed apps depend on the `application.launch` and
`application.info` privileges in `config.xml`, and may behave differently on
your TV.
