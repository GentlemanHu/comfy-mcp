import os
import shutil

home = os.path.expanduser("~")

bash_profile_content = """# ~/.bash_profile - Bash login shell configuration for macOS

# Load ~/.bashrc if present
if [ -f "$HOME/.bashrc" ]; then
    . "$HOME/.bashrc"
fi
"""

bashrc_content = """# ~/.bashrc - Bash interactive and subshell configuration

# Prevent duplicate initialization if re-sourced
if [ -z "$_BASHRC_LOADED" ]; then
    export _BASHRC_LOADED=1

    # Base environment & DevTools root
    export DEVTOOLS_ROOT="/Volumes/GodLin/Dev/Tools"

    # Homebrew (external)
    export HOMEBREW_PREFIX="$DEVTOOLS_ROOT/Homebrew"
    export HOMEBREW_LOGS="$DEVTOOLS_ROOT/Homebrew/Logs"
    export HOMEBREW_TEMP="$DEVTOOLS_ROOT/Homebrew/Temp"
    export HOMEBREW_CACHE="$DEVTOOLS_ROOT/Homebrew/Cache"
    export HOMEBREW_CASK_OPTS="--appdir=/Volumes/GodLin/Applications"
    export HOMEBREW_NO_ANALYTICS=1
    export PATH="$HOMEBREW_PREFIX/bin:$HOMEBREW_PREFIX/sbin:$PATH"

    # Standard user local bin
    export PATH="$HOME/.local/bin:$PATH"

    # XDG dirs (external)
    export XDG_CACHE_HOME="$DEVTOOLS_ROOT/xdg-cache"
    export XDG_CONFIG_HOME="$DEVTOOLS_ROOT/xdg-config"
    export XDG_DATA_HOME="$DEVTOOLS_ROOT/xdg-data"

    # Editors & CLI
    export EDITOR="code -w"
    export VISUAL="code -w"
    export PATH="/Volumes/GodLin/Applications/Visual Studio Code.app/Contents/Resources/app/bin:$PATH"

    # Antigravity
    export PATH="$HOME/.antigravity/antigravity/bin:$PATH"

    # Pyenv (external)
    export PYENV_ROOT="$DEVTOOLS_ROOT/pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    if [ -d "$PYENV_ROOT/bin" ]; then
        eval "$(pyenv init --path 2>/dev/null || true)"
        eval "$(pyenv init - 2>/dev/null || true)"
        export PATH="$PYENV_ROOT/shims:$PATH"
    fi

    # NVM & Node (external)
    export NVM_DIR="$DEVTOOLS_ROOT/nvm"
    export npm_config_cache="$DEVTOOLS_ROOT/npm-cache"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    [ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"
    export npm_config_prefix="$NVM_DIR/npm-global"
    export PATH="$NVM_DIR/npm-global/bin:$PATH"

    # FVM / Flutter (external)
    export FVM_CACHE_PATH="$DEVTOOLS_ROOT/fvm-cache"
    export PUB_CACHE="$DEVTOOLS_ROOT/dart-pub-cache"
    export PATH="$PUB_CACHE/bin:$PATH"
    export PATH="$FVM_CACHE_PATH/default/bin:$PATH"

    # Android SDK (external)
    export ANDROID_SDK_ROOT="$DEVTOOLS_ROOT/android-sdk"
    export ANDROID_HOME="$ANDROID_SDK_ROOT"
    export GRADLE_USER_HOME="$DEVTOOLS_ROOT/gradle"
    export PATH="$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"

    # Java (OpenJDK)
    if [ -d "$HOMEBREW_PREFIX/opt/openjdk" ]; then
        export JAVA_HOME="$HOMEBREW_PREFIX/opt/openjdk/libexec/openjdk.jdk/Contents/Home"
        export PATH="$JAVA_HOME/bin:$PATH"
    fi

    # Go (external)
    export GOPATH="$DEVTOOLS_ROOT/go"
    export GOMODCACHE="$GOPATH/pkg/mod"
    export GOCACHE="$DEVTOOLS_ROOT/go-cache"
    export PATH="$GOPATH/bin:$PATH"

    # Rust / Cargo (external)
    export CARGO_HOME="$DEVTOOLS_ROOT/cargo"
    export RUSTUP_HOME="$DEVTOOLS_ROOT/rustup"
    export PATH="$CARGO_HOME/bin:$PATH"
    [ -f "$DEVTOOLS_ROOT/cargo/env" ] && . "$DEVTOOLS_ROOT/cargo/env"

    # Ruby / rbenv
    export RBENV_ROOT="$DEVTOOLS_ROOT/.rbenv"
    export PATH="$RBENV_ROOT/bin:$PATH"
    if [ -d "$RBENV_ROOT/bin" ]; then
        eval "$(rbenv init - 2>/dev/null || true)"
    fi

    # Developer & Xcode
    export DEVELOPER_DIR="/Volumes/GodLin/Applications/Xcode.app/Contents/Developer"

    # Hermes & UV tools
    export UV_TOOL_DIR="$DEVTOOLS_ROOT/aienv/hermes/uv/tools"
    export UV_TOOL_BIN_DIR="$DEVTOOLS_ROOT/aienv/hermes/uv/bin"
    export PATH="$DEVTOOLS_ROOT/aienv/hermes/uv/bin:$PATH"

    # XDG env & Unity env
    [ -f "$DEVTOOLS_ROOT/xdg-data/../bin/env" ] && . "$DEVTOOLS_ROOT/xdg-data/../bin/env"
    [ -f "$HOME/.unity/env" ] && . "$HOME/.unity/env"

    # External API Keys / Tokens
    export FREESTYLE_API_KEY="E2dzudyLa8g85ZLUemBMMV-7ZV3FTUUkqMDoVc1AiPwrXZZhHS3RJnZBsyu24tWaP1U"
fi

# Interactive conveniences (only in interactive shells)
if [ -n "$PS1" ]; then
    # zoxide integration for bash
    if command -v zoxide >/dev/null 2>&1; then
        eval "$(zoxide init bash --cmd j 2>/dev/null || true)"
    fi
fi
"""

# Backup if existing
bash_profile_path = os.path.join(home, ".bash_profile")
bashrc_path = os.path.join(home, ".bashrc")

if os.path.exists(bash_profile_path):
    shutil.copyfile(bash_profile_path, bash_profile_path + ".bak")
with open(bash_profile_path, "w", encoding="utf-8") as f:
    f.write(bash_profile_content)
print("Created ~/.bash_profile")

if os.path.exists(bashrc_path):
    shutil.copyfile(bashrc_path, bashrc_path + ".bak")
with open(bashrc_path, "w", encoding="utf-8") as f:
    f.write(bashrc_content)
print("Created ~/.bashrc")
