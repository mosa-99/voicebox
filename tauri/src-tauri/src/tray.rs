//! Menu bar icon and its menu.
//!
//! The menu mirrors what menu bar dictation apps offer: a status line, start
//! and stop dictation, copy the last transcript, jump to the main pages,
//! start at login, check for updates, about and quit. Labels follow the UI
//! language (see app_menu.rs). The icon is a template mic that macOS tints;
//! it turns red while recording and filled while transcribing or speaking.
//!
//! State comes from the frontend: the main window reports the server status
//! (`set_tray_server_status`) and the dictate pill reports its state
//! (`set_tray_dictation_state`). Each change rebuilds the menu.

use std::sync::atomic::{AtomicU8, Ordering};
use std::sync::Mutex;

use tauri::image::Image;
use tauri::menu::{CheckMenuItem, Menu, MenuEvent, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, Wry};
use tauri_plugin_autostart::ManagerExt;

use crate::app_menu::labels;
use crate::background::{show_main_window, show_main_window_at};
use crate::hotkey_monitor;

const TRAY_ID: &str = "voicebox";

// Menu item ids. The app menu (app_menu.rs) reuses SETTINGS and
// CHECK_UPDATES, so both menus go through `handle_menu_event`.
pub const ITEM_TOGGLE_DICTATION: &str = "tray-toggle-dictation";
pub const ITEM_COPY_LAST: &str = "tray-copy-last";
pub const ITEM_OPEN: &str = "tray-open";
pub const ITEM_CAPTURES: &str = "tray-captures";
pub const ITEM_VOICES: &str = "tray-voices";
pub const ITEM_SETTINGS: &str = "app-settings";
pub const ITEM_LAUNCH_AT_LOGIN: &str = "tray-launch-at-login";
pub const ITEM_CHECK_UPDATES: &str = "app-check-updates";
pub const ITEM_ABOUT: &str = "tray-about";
pub const ITEM_QUIT: &str = "tray-quit";

const SERVER_STARTING: u8 = 0;
const SERVER_READY: u8 = 1;
const SERVER_OFFLINE: u8 = 2;

const DICTATION_IDLE: u8 = 0;
const DICTATION_RECORDING: u8 = 1;
const DICTATION_PROCESSING: u8 = 2;
const DICTATION_SPEAKING: u8 = 3;

static SERVER: AtomicU8 = AtomicU8::new(SERVER_STARTING);
static DICTATION: AtomicU8 = AtomicU8::new(DICTATION_IDLE);
static LANG: Mutex<String> = Mutex::new(String::new());

fn icon_bytes() -> (&'static [u8], bool) {
    // (PNG, is_template). Template images are tinted by macOS for light and
    // dark menu bars; the recording icon keeps its red.
    match DICTATION.load(Ordering::SeqCst) {
        DICTATION_RECORDING => (include_bytes!("../icons/tray-recording@2x.png"), false),
        DICTATION_PROCESSING | DICTATION_SPEAKING => {
            (include_bytes!("../icons/tray-busy@2x.png"), true)
        }
        _ => (include_bytes!("../icons/tray-idle@2x.png"), true),
    }
}

fn status_text(lang: &str) -> String {
    let l = labels(lang);
    let (dot, text) = match (
        DICTATION.load(Ordering::SeqCst),
        SERVER.load(Ordering::SeqCst),
    ) {
        (DICTATION_RECORDING, _) => ("●", l.status_recording),
        (DICTATION_PROCESSING, _) => ("●", l.status_processing),
        (DICTATION_SPEAKING, _) => ("●", l.status_speaking),
        (_, SERVER_READY) => ("●", l.status_ready),
        (_, SERVER_OFFLINE) => ("○", l.status_offline),
        _ => ("○", l.status_starting),
    };
    format!("{dot} {text}")
}

fn build_menu(app: &AppHandle, lang: &str) -> tauri::Result<Menu<Wry>> {
    let l = labels(lang);
    let ready = SERVER.load(Ordering::SeqCst) == SERVER_READY;
    let recording = DICTATION.load(Ordering::SeqCst) == DICTATION_RECORDING;
    let busy = matches!(
        DICTATION.load(Ordering::SeqCst),
        DICTATION_PROCESSING | DICTATION_SPEAKING
    );
    let version = app.package_info().version.to_string();
    let launch_at_login = app.autolaunch().is_enabled().unwrap_or(false);

    let header = MenuItem::new(app, format!("Voicebox {version}"), false, None::<&str>)?;
    let status = MenuItem::new(app, status_text(lang), false, None::<&str>)?;
    let dictation = MenuItem::with_id(
        app,
        ITEM_TOGGLE_DICTATION,
        if recording {
            l.stop_dictation
        } else {
            l.start_dictation
        },
        ready && !busy,
        None::<&str>,
    )?;
    let copy_last = MenuItem::with_id(app, ITEM_COPY_LAST, l.copy_last, ready, None::<&str>)?;
    let open = MenuItem::with_id(app, ITEM_OPEN, l.tray_open, true, None::<&str>)?;
    let captures = MenuItem::with_id(app, ITEM_CAPTURES, l.captures, true, None::<&str>)?;
    let voices = MenuItem::with_id(app, ITEM_VOICES, l.voices, true, None::<&str>)?;
    let settings = MenuItem::with_id(app, ITEM_SETTINGS, l.settings, true, Some("CmdOrCtrl+,"))?;
    let login = CheckMenuItem::with_id(
        app,
        ITEM_LAUNCH_AT_LOGIN,
        l.launch_at_login,
        true,
        launch_at_login,
        None::<&str>,
    )?;
    let updates = MenuItem::with_id(app, ITEM_CHECK_UPDATES, l.check_updates, true, None::<&str>)?;
    let about = MenuItem::with_id(app, ITEM_ABOUT, l.about, true, None::<&str>)?;
    let quit = MenuItem::with_id(app, ITEM_QUIT, l.quit, true, Some("CmdOrCtrl+Q"))?;
    let separator = || PredefinedMenuItem::separator(app);
    let (sep1, sep2, sep3, sep4) = (separator()?, separator()?, separator()?, separator()?);

    Menu::with_items(
        app,
        &[
            &header, &status, &sep1, &dictation, &copy_last, &sep2, &open, &captures, &voices,
            &settings, &sep3, &login, &updates, &about, &sep4, &quit,
        ],
    )
}

/// Rebuild the menu and icon from the current language and state.
pub fn refresh(app: &AppHandle) {
    let lang = LANG.lock().map(|l| l.clone()).unwrap_or_default();
    let Some(tray) = app.tray_by_id(TRAY_ID) else {
        return;
    };
    if let Ok(menu) = build_menu(app, &lang) {
        let _ = tray.set_menu(Some(menu));
    }
    let (bytes, template) = icon_bytes();
    if let Ok(icon) = Image::from_bytes(bytes) {
        let _ = tray.set_icon(Some(icon));
        let _ = tray.set_icon_as_template(template);
    }
}

/// Remember the UI language and relabel the menu.
pub fn set_language(app: &AppHandle, lang: &str) {
    if let Ok(mut current) = LANG.lock() {
        *current = lang.to_string();
    }
    refresh(app);
}

/// Add the menu bar icon. Not on Linux, where closing the window quits
/// anyway and a tray needs libappindicator.
pub fn create(app: &AppHandle) -> tauri::Result<()> {
    if cfg!(target_os = "linux") {
        return Ok(());
    }
    let (bytes, template) = icon_bytes();
    let builder = TrayIconBuilder::with_id(TRAY_ID)
        .tooltip("Voicebox")
        .menu(&build_menu(app, "en")?)
        .show_menu_on_left_click(true);
    #[cfg(target_os = "macos")]
    let builder = builder
        .icon(Image::from_bytes(bytes)?)
        .icon_as_template(template);
    #[cfg(not(target_os = "macos"))]
    let builder = {
        let _ = (bytes, template);
        match app.default_window_icon() {
            Some(icon) => builder.icon(icon.clone()),
            None => builder,
        }
    };
    builder.build(app)?;
    Ok(())
}

/// One handler for the menu bar menu and the app menu's extra items.
pub fn handle_menu_event(app: &AppHandle, event: &MenuEvent) {
    match event.id().as_ref() {
        ITEM_TOGGLE_DICTATION => {
            if DICTATION.load(Ordering::SeqCst) == DICTATION_RECORDING {
                hotkey_monitor::stop_dictation(app);
            } else {
                hotkey_monitor::start_dictation(app);
            }
        }
        ITEM_COPY_LAST => copy_last_transcript(),
        ITEM_OPEN => show_main_window(app),
        ITEM_CAPTURES => show_main_window_at(app, "/captures"),
        ITEM_VOICES => show_main_window_at(app, "/voices"),
        ITEM_SETTINGS => show_main_window_at(app, "/settings"),
        ITEM_ABOUT => show_main_window_at(app, "/settings/about"),
        ITEM_CHECK_UPDATES => {
            show_main_window_at(app, "/settings");
            if let Some(window) = app.get_webview_window(crate::background::MAIN_WINDOW_LABEL) {
                let _ = window.emit("tray:check-updates", ());
            }
        }
        ITEM_LAUNCH_AT_LOGIN => {
            let autolaunch = app.autolaunch();
            let result = if autolaunch.is_enabled().unwrap_or(false) {
                autolaunch.disable()
            } else {
                autolaunch.enable()
            };
            if let Err(e) = result {
                eprintln!("Could not change launch at login: {e}");
            }
            refresh(app);
        }
        ITEM_QUIT => app.exit(0),
        _ => {}
    }
}

/// Copy the newest capture's transcript (refined if there is one) to the
/// clipboard. Runs on a worker thread because it calls the local server.
fn copy_last_transcript() {
    std::thread::spawn(|| {
        let url = format!("http://127.0.0.1:{}/captures?limit=1", crate::SERVER_PORT);
        let response = reqwest::blocking::Client::builder()
            .timeout(std::time::Duration::from_secs(5))
            .build()
            .and_then(|client| client.get(url).send())
            .and_then(|r| r.json::<serde_json::Value>());
        let text = match response {
            Ok(body) => {
                let item = &body["items"][0];
                let refined = item["transcript_refined"].as_str().unwrap_or("").trim();
                let raw = item["transcript_raw"].as_str().unwrap_or("").trim();
                if refined.is_empty() { raw } else { refined }.to_string()
            }
            Err(e) => {
                eprintln!("Copy last transcript: {e}");
                return;
            }
        };
        if !text.is_empty() {
            if let Err(e) = crate::clipboard::write_text(&text) {
                eprintln!("Copy last transcript: {e}");
            }
        }
    });
}

#[tauri::command]
pub fn set_tray_server_status(app: AppHandle, status: String) {
    let value = match status.as_str() {
        "ready" => SERVER_READY,
        "offline" => SERVER_OFFLINE,
        _ => SERVER_STARTING,
    };
    if SERVER.swap(value, Ordering::SeqCst) != value {
        refresh(&app);
    }
}

/// `state` is the dictate pill state (recording, transcribing, refining,
/// speaking, completed, error, hidden).
#[tauri::command]
pub fn set_tray_dictation_state(app: AppHandle, state: String) {
    let value = match state.as_str() {
        "recording" => DICTATION_RECORDING,
        "transcribing" | "refining" => DICTATION_PROCESSING,
        "speaking" => DICTATION_SPEAKING,
        _ => DICTATION_IDLE,
    };
    if DICTATION.swap(value, Ordering::SeqCst) != value {
        refresh(&app);
    }
}
