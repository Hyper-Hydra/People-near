@echo off
chcp 65001 > nul
title FastAPI Backend Server

echo ====================================
echo   Запуск бэкенда Общежитие №1...
echo ====================================

:: Переход в папку, где лежит этот батник
cd /d "%~dp0"

:: Проверка наличия виртуального окружения
if not exist "venv\Scripts\activate.bat" (
    echo [ОШИБКА] Папка venv не найдена! Создай виртуальное окружение.
    pause
    exit /b
)

:: Активация виртуального окружения и запуск сервера
call venv\Scripts\activate.bat
python main.py

pause