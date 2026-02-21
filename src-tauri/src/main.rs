// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{Manager, State};
use tauri_plugin_shell::ShellExt;

/// Holds the backend port once discovered from sidecar stdout.
struct BackendState {
    port: Mutex<Option<u16>>,
}

/// Tauri command: return the backend port to the frontend.
#[tauri::command]
fn get_backend_port(state: State<BackendState>) -> Option<u16> {
    *state.port.lock().unwrap()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendState {
            port: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .setup(|app| {
            let handle = app.handle().clone();

            // Spawn the Python sidecar
            let sidecar = handle
                .shell()
                .sidecar("ashai-server")
                .expect("failed to create sidecar command");

            let (mut rx, _child) = sidecar.spawn().expect("failed to spawn sidecar");

            // Read stdout in a background task to find PORT:<n>
            let handle_clone = handle.clone();
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;

                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let text = String::from_utf8_lossy(&line);
                            let text = text.trim();
                            if let Some(port_str) = text.strip_prefix("PORT:") {
                                if let Ok(port) = port_str.parse::<u16>() {
                                    // Store port in state
                                    let state = handle_clone.state::<BackendState>();
                                    *state.port.lock().unwrap() = Some(port);

                                    // Emit event to all webview windows
                                    let _ = handle_clone.emit("backend-ready", port);
                                    println!("Backend ready on port {}", port);
                                }
                            } else {
                                println!("[sidecar] {}", text);
                            }
                        }
                        CommandEvent::Stderr(line) => {
                            let text = String::from_utf8_lossy(&line);
                            eprint!("[sidecar] {}", text);
                        }
                        CommandEvent::Terminated(status) => {
                            eprintln!("Sidecar terminated: {:?}", status);
                            break;
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running AshAI");
}
