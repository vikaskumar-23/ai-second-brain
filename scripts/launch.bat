@echo off
cd /d "%~dp0.."
if "%~1"=="" (
    claude "/inbox-digest"
) else (
    claude "%~1"
)
