#!/bin/bash

echo "=================================================="
echo "   Installing Deno JavaScript Runtime"
echo "=================================================="
echo ""
echo "Deno is required for YouTube signature solving."
echo "This will install Deno to ~/.deno (or DENO_INSTALL if set)."
echo ""

# Check if Deno is already installed
if command -v deno &> /dev/null; then
    echo "[OK] Deno is already installed!"
    deno --version
    echo ""
    echo "Deno is ready to use with yt-dlp."
    exit 0
fi

echo "[INFO] Installing Deno..."
echo ""

# Install Deno using official install script (Linux/macOS)
curl -fsSL https://deno.land/install.sh | sh

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to install Deno automatically."
    echo ""
    echo "Please install Deno manually:"
    echo "  1. Visit: https://docs.deno.com/runtime/getting_started/installation/"
    echo "  2. Or run: curl -fsSL https://deno.land/install.sh | sh"
    echo "  3. Add ~/.deno/bin to your PATH (e.g. in ~/.bashrc or ~/.zshrc)"
    echo ""
    exit 1
fi

# Add Deno to PATH for current session (default install is ~/.deno/bin)
export DENO_INSTALL="${DENO_INSTALL:-$HOME/.deno}"
export PATH="$DENO_INSTALL/bin:$PATH"

echo ""
echo "[INFO] Verifying installation..."
if command -v deno &> /dev/null; then
    echo "[OK] Deno installed successfully!"
    deno --version
    echo ""
    echo "IMPORTANT: Add Deno to your PATH permanently."
    echo "Deno is installed to: $DENO_INSTALL/bin"
    echo ""
    echo "Add to ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\"\$HOME/.deno/bin:\$PATH\""
    echo ""
    echo "Then run: source ~/.bashrc   (or source ~/.zshrc)"
    echo ""
else
    echo "[WARNING] Deno was installed but not found in PATH."
    echo "Add to your shell config (~/.bashrc or ~/.zshrc):"
    echo "  export PATH=\"\$HOME/.deno/bin:\$PATH\""
    echo ""
    echo "Then open a new terminal or run: source ~/.bashrc"
    echo ""
fi

echo "=================================================="
echo "        Deno Installation Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Add ~/.deno/bin to PATH (see above) and restart terminal if needed"
echo "  2. Verify: deno --version"
echo "  3. Run your music downloader - it will use Deno automatically"
echo ""
