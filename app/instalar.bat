@echo off
chcp 65001 >nul
title SermonCut - instalacao
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
