#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声笔词库工具 - Android APP
一键将手机通讯录转换为Rime输入法词库

功能：
- 自动读取手机通讯录
- 生成声笔编码词库
- 自动备份原有词库
- 一键部署到Rime目录
"""

import os
import re
import json
import quopri
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.metrics import dp

from pypinyin import lazy_pinyin, Style


# ============================================================
# 核心功能模块
# ============================================================

class ContactsReader:
    """通讯录读取器"""
    
    @staticmethod
    def get_contacts_db_path():
        """获取通讯录数据库路径"""
        paths = [
            '/data/data/com.android.providers.contacts/databases/contacts2.db',
            '/data/user/0/com.android.providers.contacts/databases/contacts2.db',
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        return None
    
    @staticmethod
    def read_from_db():
        """从数据库读取联系人"""
        db_path = ContactsReader.get_contacts_db_path()
        if not db_path:
            return [], "无法访问通讯录数据库"
        
        names = []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.data1
                FROM data d
                JOIN raw_contacts r ON d.raw_contact_id = r._id
                WHERE d.mimetype_id IN (
                    SELECT _id FROM mimetypes WHERE mimetype = 'vnd.android.cursor.item/name'
                )
                AND d.data1 IS NOT NULL
                AND d.data1 != ''
            """)
            for row in cursor.fetchall():
                name = row[0].strip()
                if name and len(name) >= 2:
                    names.append(name)
            conn.close()
            return list(set(names)), f"成功读取 {len(names)} 个联系人"
        except Exception as e:
            return [], f"读取失败: {str(e)}"
    
    @staticmethod
    def read_from_vcf(vcf_path):
        """从VCF文件读取联系人"""
        names = []
        try:
            with open(vcf_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped.startswith('FN'):
                        continue
                    fn_match = re.search(
                        r'FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:([^\n\r]+)',
                        stripped
                    )
                    if fn_match:
                        try:
                            bs = fn_match.group(1).strip().encode('latin-1')
                            name = quopri.decodestring(bs).decode('utf-8')
                        except:
                            continue
                    else:
                        fn_match = re.search(r'FN[^:]*:(.+)', stripped)
                        if fn_match:
                            name = fn_match.group(1).strip()
                        else:
                            continue
                    if name and len(name) >= 2:
                        names.append(name)
            return list(set(names)), f"成功读取 {len(names)} 个联系人"
        except Exception as e:
            return [], f"读取失败: {str(e)}"


class ShengbiEncoder:
    """声笔编码生成器"""
    
    @staticmethod
    def encode(name):
        """生成声笔编码"""
        pinyins = lazy_pinyin(name, style=Style.NORMAL)
        shengmus = lazy_pinyin(name, style=Style.INITIALS, strict=False)
        
        if not pinyins:
            return None
        
        first_shengmu = shengmus[0] if shengmus[0] else pinyins[0][0]
        code = first_shengmu.lower()
        for py in pinyins[1:]:
            if py:
                code += py[0].lower()
        return code


class DictProcessor:
    """词库处理器"""
    
    @staticmethod
    def parse_dict(dict_path):
        """解析词库"""
        word_to_code = {}
        code_to_word = {}
        
        if not os.path.exists(dict_path):
            return word_to_code, code_to_word
        
        with open(dict_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 2:
                    word_to_code[parts[0].strip()] = parts[1].strip()
                    code_to_word[parts[1].strip()] = parts[0].strip()
        
        return word_to_code, code_to_word
    
    @staticmethod
    def is_valid_chinese_name(name):
        """判断是否为有效中文名"""
        return bool(re.match(r'^[\u4e00-\u9fa5]{2,4}$', name))
    
    @staticmethod
    def process(names, existing_dict_path, output_path):
        """处理并生成词库"""
        # 读取现有词库
        existing_words, existing_codes = DictProcessor.parse_dict(existing_dict_path)
        
        # 筛选新联系人
        new_names = [
            name for name in names
            if DictProcessor.is_valid_chinese_name(name)
            and name not in existing_words
        ]
        
        # 生成编码
        used_codes = set(existing_codes.keys())
        new_entries = []
        
        for name in sorted(new_names):
            base_code = ShengbiEncoder.encode(name)
            if not base_code:
                continue
            
            code = base_code
            if code in used_codes:
                suffix = 1
                while f"{base_code}{suffix}" in used_codes:
                    suffix += 1
                code = f"{base_code}{suffix}"
            
            used_codes.add(code)
            new_entries.append((name, code))
        
        # 生成输出内容
        lines = []
        if os.path.exists(existing_dict_path):
            with open(existing_dict_path, 'r', encoding='utf-8') as f:
                lines.append(f.read().rstrip())
            lines.append("")
            lines.append(f"# 通讯录新增联系人 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        
        for name, code in new_entries:
            lines.append(f"{name}\t{code}")
        
        # 写入文件
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return {
            'total': len(names),
            'existing': len(existing_words),
            'new': len(new_entries),
            'entries': new_entries
        }


class FileManager:
    """文件管理器"""
    
    @staticmethod
    def backup(file_path):
        """备份文件"""
        if not os.path.exists(file_path):
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{file_path}.backup_{timestamp}"
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    @staticmethod
    def copy_with_backup(source, target_dir, new_name=None):
        """复制并备份"""
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_file = target_dir / (new_name or Path(source).name)
        
        # 备份
        backup_path = None
        if target_file.exists():
            backup_path = FileManager.backup(str(target_file))
        
        # 复制
        shutil.copy2(source, target_file)
        
        return str(target_file), backup_path


# ============================================================
# 界面屏幕
# ============================================================

class HomeScreen(Screen):
    """主页"""
    
    status_text = StringProperty("准备就绪")
    progress_value = NumericProperty(0)
    is_processing = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.contacts = []
        self.result = None
    
    def on_enter(self):
        """进入页面时更新状态"""
        app = App.get_running_app()
        self.ids.dict_path_label.text = f"词库路径: {app.config.get('dict_path', '未设置')}"
        self.ids.rime_dir_label.text = f"Rime目录: {app.config.get('rime_dir', '未设置')}"
    
    def read_contacts(self):
        """读取通讯录"""
        if self.is_processing:
            return
        
        self.is_processing = True
        self.status_text = "正在读取通讯录..."
        self.progress_value = 20
        
        Clock.schedule_once(self._do_read_contacts, 0.1)
    
    def _do_read_contacts(self, dt):
        """执行读取"""
        app = App.get_running_app()
        source = app.config.get('contact_source', 'auto')
        
        if source == 'vcf':
            vcf_path = app.config.get('vcf_path', '')
            if not vcf_path or not os.path.exists(vcf_path):
                self.show_error("请先在设置中指定VCF文件路径")
                self.is_processing = False
                return
            self.contacts, msg = ContactsReader.read_from_vcf(vcf_path)
        else:
            self.contacts, msg = ContactsReader.read_from_db()
        
        self.progress_value = 50
        self.status_text = msg
        
        if self.contacts:
            self.ids.contact_count_label.text = f"已读取: {len(self.contacts)} 个联系人"
            self.ids.process_btn.disabled = False
        else:
            self.show_error(msg)
        
        self.is_processing = False
        self.progress_value = 100
    
    def process_dict(self):
        """处理词库"""
        if self.is_processing or not self.contacts:
            return
        
        self.is_processing = True
        self.status_text = "正在处理词库..."
        self.progress_value = 20
        
        Clock.schedule_once(self._do_process, 0.1)
    
    def _do_process(self, dt):
        """执行处理"""
        app = App.get_running_app()
        dict_path = app.config.get('dict_path', '/storage/emulated/0/rime/sbzdy.txt')
        output_path = '/data/user/work/sbzdy_updated.txt'
        
        try:
            self.result = DictProcessor.process(
                self.contacts, dict_path, output_path
            )
            
            self.progress_value = 60
            self.status_text = f"新增 {self.result['new']} 个词条"
            
            # 备份并复制
            rime_dir = app.config.get('rime_dir', '/storage/emulated/0/rime')
            target_file, backup_file = FileManager.copy_with_backup(
                output_path, rime_dir, 'sbzdy.txt'
            )
            
            self.progress_value = 100
            
            if backup_file:
                self.status_text = f"完成！新增 {self.result['new']} 个词条\n已备份: {backup_file}"
            else:
                self.status_text = f"完成！新增 {self.result['new']} 个词条"
            
            # 保存历史
            self.save_history(self.result)
            
            # 启用预览按钮
            self.ids.preview_btn.disabled = False
            
        except Exception as e:
            self.show_error(f"处理失败: {str(e)}")
        
        self.is_processing = False
    
    def save_history(self, result):
        """保存历史记录"""
        app = App.get_running_app()
        history_file = os.path.join(app.user_data_dir, 'history.json')
        
        history = []
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
        
        history.insert(0, {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'total': result['total'],
            'new': result['new']
        })
        
        # 只保留最近20条
        history = history[:20]
        
        with open(history_file, 'w') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def show_error(self, msg):
        """显示错误"""
        popup = Popup(
            title='错误',
            content=Label(text=msg),
            size_hint=(0.8, 0.3)
        )
        popup.open()
    
    def go_preview(self):
        """跳转到预览页"""
        if self.result and self.result['entries']:
            app = App.get_running_app()
            app.sm.get_screen('preview').set_entries(self.result['entries'])
            self.manager.current = 'preview'


class SettingsScreen(Screen):
    """设置页"""
    
    def on_enter(self):
        """加载设置"""
        app = App.get_running_app()
        
        # 词库路径
        self.ids.dict_path_input.text = app.config.get(
            'dict_path', '/storage/emulated/0/rime/sbzdy.txt'
        )
        
        # Rime目录
        self.ids.rime_dir_input.text = app.config.get(
            'rime_dir', '/storage/emulated/0/rime'
        )
        
        # VCF路径
        self.ids.vcf_path_input.text = app.config.get('vcf_path', '')
        
        # 通讯录来源
        source = app.config.get('contact_source', 'auto')
        self.ids.source_spinner.text = {
            'auto': '自动（优先数据库）',
            'db': '通讯录数据库',
            'vcf': 'VCF文件'
        }.get(source, '自动（优先数据库）')
    
    def save_settings(self):
        """保存设置"""
        app = App.get_running_app()
        
        app.config['dict_path'] = self.ids.dict_path_input.text
        app.config['rime_dir'] = self.ids.rime_dir_input.text
        app.config['vcf_path'] = self.ids.vcf_path_input.text
        
        source_map = {
            '自动（优先数据库）': 'auto',
            '通讯录数据库': 'db',
            'VCF文件': 'vcf'
        }
        app.config['contact_source'] = source_map.get(
            self.ids.source_spinner.text, 'auto'
        )
        
        app.save_config()
        
        popup = Popup(
            title='成功',
            content=Label(text='设置已保存'),
            size_hint=(0.6, 0.2)
        )
        popup.open()


class PreviewScreen(Screen):
    """预览页"""
    
    def set_entries(self, entries):
        """设置词条列表"""
        self.ids.entries_container.clear_widgets()
        
        for name, code in entries[:100]:  # 只显示前100条
            item = BoxLayout(size_hint_y=None, height=dp(40))
            item.add_widget(Label(text=name, size_hint_x=0.5))
            item.add_widget(Label(text=code, size_hint_x=0.5))
            self.ids.entries_container.add_widget(item)
        
        if len(entries) > 100:
            more = Label(
                text=f"... 还有 {len(entries) - 100} 条",
                size_hint_y=None, height=dp(40)
            )
            self.ids.entries_container.add_widget(more)


class HistoryScreen(Screen):
    """历史记录页"""
    
    def on_enter(self):
        """加载历史"""
        app = App.get_running_app()
        history_file = os.path.join(app.user_data_dir, 'history.json')
        
        self.ids.history_container.clear_widgets()
        
        if not os.path.exists(history_file):
            self.ids.history_container.add_widget(
                Label(text="暂无历史记录", size_hint_y=None, height=dp(40))
            )
            return
        
        with open(history_file, 'r') as f:
            history = json.load(f)
        
        for item in history:
            row = BoxLayout(size_hint_y=None, height=dp(40))
            row.add_widget(Label(text=item['time'], size_hint_x=0.4))
            row.add_widget(Label(text=f"新增 {item['new']} 条", size_hint_x=0.6))
            self.ids.history_container.add_widget(row)


# ============================================================
# 主应用
# ============================================================

class ShengbiApp(App):
    """主应用"""
    
    def build(self):
        self.title = "声笔词库工具"
        
        # 创建屏幕管理器
        self.sm = ScreenManager()
        self.sm.add_widget(HomeScreen(name='home'))
        self.sm.add_widget(SettingsScreen(name='settings'))
        self.sm.add_widget(PreviewScreen(name='preview'))
        self.sm.add_widget(HistoryScreen(name='history'))
        
        # 加载配置
        self.config = self.load_config()
        
        return self.sm
    
    def load_config(self):
        """加载配置"""
        config_file = os.path.join(self.user_data_dir, 'config.json')
        
        default_config = {
            'dict_path': '/storage/emulated/0/rime/sbzdy.txt',
            'rime_dir': '/storage/emulated/0/rime',
            'vcf_path': '',
            'contact_source': 'auto'
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                saved = json.load(f)
                default_config.update(saved)
        
        return default_config
    
    def save_config(self):
        """保存配置"""
        config_file = os.path.join(self.user_data_dir, 'config.json')
        with open(config_file, 'w') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    ShengbiApp().run()
