# Thin launcher. All app logic lives in court_cataloguer/.
# Run directly during development, or freeze with PyInstaller for deployment.

from court_cataloguer.app import main

if __name__ == "__main__":
    main()
