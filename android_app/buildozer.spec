[app]

# 应用信息
title = 声笔词库工具
package.name = shengbi
package.domain = org.shengbi
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0
requirements = python3,kivy,pypinyin,sqlite3
orientation = portrait

# 图标和启动画面（可选）
#icon.filename = icon.png
#presplash.filename = presplash.png

# 权限
android.permissions = READ_CONTACTS,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# API版本
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33

# 架构
android.archs = arm64-v8a,armeabi-v7a

# 接受SDK许可
android.accept_sdk_license = True

# 全屏模式
fullscreen = 0

# 应用主题
android.allow_backup = True

# 崩溃报告
#android.logcat_filters = *:D python:D

# 构建选项
[buildozer]
log_level = 2
warn_on_root = 1
