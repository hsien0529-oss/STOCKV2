@echo off
chcp 65001 >nul
echo ========================================================
echo       GitHub 上傳小幫手 (GitHub Upload Helper)
echo ========================================================
echo.

:ASK_MSG
set /p "commit_msg=請輸入更新內容 (Commit Message): "
if "%commit_msg%"=="" goto ASK_MSG

echo.
echo --------------------------------------------------------
echo [1/3] 正在加入檔案 (Adding files)...
git add .

echo.
echo [2/3] 正在提交變更 (Committing)...
git commit -m "%commit_msg%"

echo.
echo [3/3] 正在上傳至 GitHub (Pushing)...
git push

echo.
echo ========================================================
if %errorlevel% equ 0 (
    echo    ✅ 上傳成功！ (Upload Successful)
) else (
    echo    ❌ 上傳失敗，請檢查網路或是錯誤訊息。
)
echo ========================================================
echo.
pause
