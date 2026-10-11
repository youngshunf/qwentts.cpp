$ErrorActionPreference = 'Stop'
python "$PSScriptRoot/build-library.py" --platform windows-x86_64 @args
exit $LASTEXITCODE
