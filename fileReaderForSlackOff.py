import sys
import os
import re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTextEdit, QMenu, QAction,
                             QFileDialog, QMessageBox, QColorDialog, QFontDialog,
                             QInputDialog, QSystemTrayIcon, QShortcut)
from PyQt5.QtCore import Qt, QUrl, QTimer, QSize, QPoint
from PyQt5.QtGui import (QDragEnterEvent, QDropEvent, QTextCursor, QKeySequence,
                         QColor, QFont, QIcon, QPixmap, QPen, QPainter)
import datetime

class TextReader(QMainWindow):
    def __init__(self):
        super().__init__()
        # 1. 初始化基础配置参数
        self.transparency = 80  # 默认透明度80%
        self.hide_delay = 5000
        self.is_hidden = False
        self.is_empty = True  # 空文本状态标志
        self.font = QFont("SimHei", 14)  # 默认字体
        self.text_color = QColor(0, 0, 0)  # 黑色文本
        self.text_color.setAlpha(255)  # 文本强制不透明
        self.bg_color = QColor(255, 255, 255, 204)  # 白色半透明背景
        self.drag_start_position = None

        # 2. 初始化UI
        self.initUI()

        # 3. 初始化定时器（关键：在使用前创建）
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.check_and_hide_window)

        # 4. 文件路径配置
        self.bookmark_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ini", "bookmark.txt")
        self.recent_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ini", "recent.txt")
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ini", "config.txt")
        self.current_file = ""

        # 5. 确保配置目录存在
        if not os.path.exists(os.path.dirname(self.bookmark_path)):
            os.makedirs(os.path.dirname(self.bookmark_path))

        # 6. 加载配置
        self.load_config()

        # 7. 加载最近文件
        self.load_recent_file()

        # 8. 设置快捷键
        self.show_shortcut = QShortcut(QKeySequence("Ctrl+Alt+T"), self)
        self.show_shortcut.setContext(Qt.ApplicationShortcut)  # 全局快捷键
        self.show_shortcut.activated.connect(self.toggle_window_visibility)

        self.exit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.exit_shortcut.activated.connect(self.close)

        # 9. 初始化系统托盘
        self.init_system_tray()

        # 10. 更新空文本状态（现在hide_timer已创建）
        self.update_empty_state()

        # 11. 确保窗口可见
        self.force_show_window()

    def initUI(self):
        """初始化用户界面"""
        # 设置窗口属性
        self.setWindowTitle("文本阅读器")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # 透明背景

        # 创建文本编辑区域
        self.text_edit = QTextEdit(self)
        self.text_edit.setAcceptDrops(True)
        self.text_edit.setReadOnly(True)
        self.text_edit.setTextInteractionFlags(Qt.NoTextInteraction)  # 禁止文本交互
        self.text_edit.setStyleSheet(self.get_style_sheet())
        self.text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self.show_context_menu)

        # 隐藏滚动条
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 设置为中心部件
        self.setCentralWidget(self.text_edit)

        # 安装事件过滤器
        self.installEventFilter(self)
        self.text_edit.installEventFilter(self)

    def get_style_sheet(self):
        """生成样式表"""
        font_family = self.font.family() if self.font else "SimHei"
        font_size = f"{self.font.pointSize()}pt" if self.font else "14pt"

        return f"""
            QTextEdit {{
                background-color: rgba({self.bg_color.red()}, {self.bg_color.green()}, {self.bg_color.blue()}, {self.bg_color.alpha()});
                color: rgba({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()}, 255);
                border: none;
                padding: 20px;
                font-family: "{font_family}";
                font-size: {font_size};
                caret-color: transparent;
                selection-background-color: transparent;
                selection-color: rgba({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()}, 255);
            }}
            QMainWindow, QWidget {{
                background-color: transparent;
            }}
        """

    def eventFilter(self, obj, event):
        """事件过滤器"""
        # 处理窗口级鼠标事件（拖动）
        if obj is self:
            if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                self.drag_start_position = event.pos()
                self.hide_timer.stop()
                self.hide_timer.start(self.hide_delay)
                return True

            elif event.type() == event.MouseMove and event.buttons() == Qt.LeftButton and self.drag_start_position:
                delta = event.pos() - self.drag_start_position
                self.move(self.mapToGlobal(delta))
                return True

            elif event.type() == event.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.drag_start_position = None
                return True

        # 处理文本编辑区域事件（滚动）
        elif obj is self.text_edit:
            if event.type() == event.Wheel:
                scroll_bar = self.text_edit.verticalScrollBar()
                if event.angleDelta().y() < 0:
                    scroll_bar.setValue(scroll_bar.value() + 50)
                else:
                    scroll_bar.setValue(scroll_bar.value() - 50)
                return True

            elif event.type() == event.ContextMenu:
                self.show_context_menu(event.globalPos())
                return True

            # 拦截文本区域的鼠标事件，传递给窗口处理
            elif event.type() in [event.MouseButtonPress, event.MouseMove, event.MouseButtonRelease]:
                return self.eventFilter(self, event)

        return super().eventFilter(obj, event)

    def show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu(self)

        # 文件操作
        import_action = QAction("导入书籍", self)
        import_action.triggered.connect(self.open_file)
        menu.addAction(import_action)

        menu.addSeparator()

        # 文本设置
        font_action = QAction("设置字体", self)
        font_action.triggered.connect(self.set_font)
        menu.addAction(font_action)

        text_color_action = QAction("设置文本颜色", self)
        text_color_action.triggered.connect(self.set_text_color)
        menu.addAction(text_color_action)

        bg_color_action = QAction("设置背景颜色", self)
        bg_color_action.triggered.connect(self.set_bg_color)
        menu.addAction(bg_color_action)

        menu.addSeparator()

        # 透明度设置
        trans_menu = menu.addMenu("透明度")

        trans100_action = QAction("100%", self)
        trans100_action.triggered.connect(lambda: self.set_transparency(100))
        trans_menu.addAction(trans100_action)

        trans90_action = QAction("90%", self)
        trans90_action.triggered.connect(lambda: self.set_transparency(90))
        trans_menu.addAction(trans90_action)

        trans70_action = QAction("70%", self)
        trans70_action.triggered.connect(lambda: self.set_transparency(70))
        trans_menu.addAction(trans70_action)

        trans50_action = QAction("50%", self)
        trans50_action.triggered.connect(lambda: self.set_transparency(50))
        trans_menu.addAction(trans50_action)

        menu.addSeparator()

        # 书签功能
        bookmark_menu = menu.addMenu("书签")

        add_bookmark_action = QAction("添加书签", self)
        add_bookmark_action.triggered.connect(self.add_bookmark)
        bookmark_menu.addAction(add_bookmark_action)

        # 显示已有书签
        if os.path.exists(self.bookmark_path):
            bookmark_menu.addSeparator()
            with open(self.bookmark_path, 'r', encoding='utf-8') as f:
                bookmarks = [line.strip() for line in f if line.strip()]

            for i, bookmark in enumerate(bookmarks[:10]):
                if len(bookmark) > 30:
                    bookmark = bookmark[:27] + "..."

                action = QAction(f"书签 {i + 1}: {bookmark}", self)
                action.triggered.connect(lambda checked, b=bookmark: self.jump_to_bookmark(b))
                bookmark_menu.addAction(action)

        menu.addSeparator()

        # 窗口控制菜单
        window_menu = menu.addMenu("窗口控制")

        resize_action = QAction("调整窗口大小", self)
        resize_action.triggered.connect(self.resize_window)
        window_menu.addAction(resize_action)

        # 退出程序
        exit_action = QAction("退出 (&Q)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)

        # 显示菜单
        menu.exec_(self.text_edit.mapToGlobal(position))

    def resize_window(self):
        """调整窗口大小"""
        current_width = self.width()
        current_height = self.height()

        new_size, ok = QInputDialog.getText(
            self,
            "调整窗口大小",
            f"请输入窗口尺寸 (宽x高，当前: {current_width}x{current_height}):",
            text=f"{current_width}x{current_height}"
        )

        if ok and new_size:
            try:
                width, height = map(int, new_size.split('x'))

                # 验证输入有效性
                if width > 50 and height > 50:
                    self.resize(width, height)
                    self.save_config()  # 保存新尺寸
                else:
                    self.show_error_message("窗口尺寸过小，请输入大于50的数值")
            except ValueError:
                self.show_error_message("输入格式错误，请使用'宽x高'格式（例如：800x600）")

    def set_font(self):
        """设置字体"""
        font, ok = QFontDialog.getFont(self.font, self, "选择字体")
        if ok:
            self.font = font
            self.text_edit.setStyleSheet(self.get_style_sheet())
            self.save_config()

    def set_text_color(self):
        """设置文本颜色"""
        color = QColorDialog.getColor(self.text_color, self, "选择文本颜色")
        if color.isValid():
            self.text_color = color
            self.text_color.setAlpha(255)  # 确保文本不透明
            self.text_edit.setStyleSheet(self.get_style_sheet())
            self.save_config()

    def set_bg_color(self):
        """设置背景颜色"""
        color = QColorDialog.getColor(self.bg_color, self, "选择背景颜色")
        if color.isValid():
            self.bg_color = color
            self.bg_color.setAlpha(int(255 * self.transparency / 100))
            self.text_edit.setStyleSheet(self.get_style_sheet())
            self.save_config()

    def set_transparency(self, value):
        """设置透明度"""
        self.transparency = value
        alpha = int(255 * value / 100)
        self.bg_color.setAlpha(alpha)
        self.text_edit.setStyleSheet(self.get_style_sheet())
        self.save_config()

    def add_bookmark(self):
        """添加书签"""
        cursor = self.text_edit.textCursor()
        selected_text = cursor.selectedText()

        if not selected_text:
            cursor.movePosition(cursor.StartOfLine)
            cursor.movePosition(cursor.EndOfLine, cursor.KeepAnchor)
            selected_text = cursor.selectedText()

        if selected_text:
            try:
                with open(self.bookmark_path, 'a', encoding='utf-8') as file:
                    file.write(f"{selected_text[:100]}\n")

                self.show_message("成功", "书签已添加")
            except Exception as e:
                self.show_error_message(f"无法保存书签: {str(e)}")

    def jump_to_bookmark(self, bookmark_text):
        """跳转到书签位置"""
        index = self.text_edit.toPlainText().find(bookmark_text)
        if index != -1:
            cursor = self.text_edit.textCursor()
            cursor.setPosition(index)
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()
            self.highlight_text(index, len(bookmark_text))
        else:
            self.show_error_message(f"未找到书签内容")

    def highlight_text(self, start, length):
        """高亮显示文本"""
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + length, cursor.KeepAnchor)
        self.text_edit.setTextCursor(cursor)

    def init_system_tray(self):
        """初始化系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "错误", "系统不支持系统托盘功能!")
            QApplication.quit()
            return

        # 创建托盘图标
        self.tray_icon = QSystemTrayIcon(self)

        # 创建默认图标
        icon = QIcon()
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(Qt.gray, 2))
        painter.drawRect(4, 4, 16, 16)
        painter.end()
        icon.addPixmap(pixmap)

        # 设置图标
        system_icon = QIcon.fromTheme("utilities-terminal")
        self.tray_icon.setIcon(system_icon if not system_icon.isNull() else icon)
        self.tray_icon.setToolTip("文本阅读器")

        # 创建托盘菜单
        self.tray_menu = QMenu(self)

        # 状态提示
        # 创建状态显示动作（只读）
        self.status_action = QAction("状态: 等待文件", self)
        self.status_action.setEnabled(False)  # 不可点击

        # 添加到菜单
        self.tray_menu.addAction(self.status_action)
        self.tray_menu.addSeparator()
        # 显示/隐藏窗口
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_window_from_tray)
        self.tray_menu.addAction(show_action)

        hide_action = QAction("隐藏窗口", self)
        hide_action.triggered.connect(self.hide_window_to_tray)
        self.tray_menu.addAction(hide_action)

        self.tray_menu.addSeparator()
        #选择文件
        select_file_action = QAction("选择文件", self)
        select_file_action.triggered.connect(self.open_file_from_tray)
        self.tray_menu.insertAction(show_action, select_file_action)
        # 退出程序
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.exit_app)
        self.tray_menu.addAction(exit_action)

        # 设置托盘菜单
        self.tray_icon.setContextMenu(self.tray_menu)

        # 托盘点击事件
        self.tray_icon.activated.connect(self.tray_icon_activated)

        # 显示托盘图标
        self.tray_icon.show()

    def show_window_from_tray(self):
        """从托盘显示窗口"""
        self.show()
        self.raise_()  # 窗口置顶
        self.activateWindow()
        self.show_window()  # 调用显示窗口方法
        self.update_tray_status()

    def hide_window_to_tray(self):
        """隐藏窗口到托盘"""
        self.hide()  # 隐藏窗口
        self.is_hidden = True
        self.tray_icon.showMessage(
            "文本阅读器",
            "程序已最小化到系统托盘",
            QSystemTrayIcon.Information,
            2000
        )
        self.update_tray_status()

    def tray_icon_activated(self, reason):
        """托盘图标激活事件处理"""
        # 左键点击显示/隐藏窗口
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide_window_to_tray()
            else:
                self.show_window_from_tray()

        # 双击也显示窗口
        elif reason == QSystemTrayIcon.DoubleClick:
            self.show_window_from_tray()

    def exit_app(self):
        """从托盘退出应用程序"""
        self.tray_icon.hide()  # 隐藏托盘图标
        self.close()  # 关闭窗口
        QApplication.quit()  # 退出应用

    def update_empty_state(self):
        """更新空文本状态"""
        content = self.text_edit.toPlainText().strip()
        self.is_empty = len(content) == 0

        if self.is_empty:
            # 显示拖放提示
            self.text_edit.setHtml("""
                <div style="text-align: center; vertical-align: middle; color: #888888; font-size: 14pt; padding: 50px;">
                    <p>拖放TXT文件到此处开始阅读</p>
                    <p style="font-size: 10pt; margin-top: 20px;">快捷键: Ctrl+Alt+T (显示/隐藏窗口)</p>
                </div>
            """)
            # 空文本时禁用自动隐藏
            self.hide_timer.stop()
        else:
            # 有内容时启用自动隐藏
            self.hide_timer.start(self.hide_delay)

        # 更新托盘状态
        self.update_tray_status()

    def check_and_hide_window(self):
        """条件化隐藏窗口"""
        if not self.is_empty and not self.is_hidden:
            self.hide_window()

    def hide_window(self):
        """隐藏窗口"""
        if not hasattr(self, 'original_bg_alpha'):
            self.original_bg_alpha = self.bg_color.alpha()
            self.original_text_alpha = self.text_color.alpha()

        self.bg_color.setAlpha(0)
        self.text_edit.setStyleSheet(self.get_style_sheet())
        self.is_hidden = True
        self.hide_timer.stop()
        self.update_tray_status()

    def show_window(self):
        """显示窗口"""
        if hasattr(self, 'original_bg_alpha'):
            self.bg_color.setAlpha(self.original_bg_alpha)
            self.text_edit.setStyleSheet(self.get_style_sheet())
            self.is_hidden = False

            if not self.is_empty:
                self.hide_timer.start(self.hide_delay)

            self.tray_icon.showMessage(
                "文本阅读器",
                "窗口已显示",
                QSystemTrayIcon.Information,
                1000
            )
        else:
            self.is_hidden = False
            if not self.is_empty:
                self.hide_timer.start(self.hide_delay)

        self.update_tray_status()

    def toggle_window_visibility(self):
        """切换窗口可见性"""
        if self.isVisible() and not self.is_empty:
            self.hide_window()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self.show_window()

    # 其他必要方法（略，保持原有实现）
    def set_transparency(self, value):
        self.transparency = value
        alpha = int(255 * value / 100)
        self.bg_color.setAlpha(alpha)
        self.text_edit.setStyleSheet(self.get_style_sheet())
        self.save_config()

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("transparency="):
                            self.transparency = max(30, min(100, int(line.split("=")[1])))
                        elif line.startswith("window_width="):
                            self.window_width = max(300, min(2000, int(line.split("=")[1])))
                        elif line.startswith("window_height="):
                            self.window_height = max(200, min(1500, int(line.split("=")[1])))
                        elif line.startswith("window_x="):
                            self.window_x = int(line.split("=")[1])
                        elif line.startswith("window_y="):
                            self.window_y = int(line.split("=")[1])
                        elif line.startswith("font="):
                            font_family = line.split("=")[1]
                            if self.font:
                                self.font.setFamily(font_family)
                            else:
                                self.font = QFont(font_family, 14)
                        elif line.startswith("font_size="):
                            font_size = int(line.split("=")[1])
                            if self.font:
                                self.font.setPointSize(font_size)
                            else:
                                self.font = QFont("SimHei", font_size)
                        elif line.startswith("text_color="):
                            self.text_color = QColor(line.split("=")[1])
                            self.text_color.setAlpha(255)  # 确保文本不透明
                        elif line.startswith("bg_color="):
                            self.bg_color = QColor(line.split("=")[1])

                # 应用窗口位置和尺寸
                if hasattr(self, 'window_x') and hasattr(self, 'window_y'):
                    screen_geometry = QApplication.desktop().availableGeometry()
                    x = max(0, min(self.window_x, screen_geometry.width() - 300))
                    y = max(0, min(self.window_y, screen_geometry.height() - 200))
                    self.move(x, y)

                if hasattr(self, 'window_width') and hasattr(self, 'window_height'):
                    self.resize(self.window_width, self.window_height)

                # 应用透明度
                self.bg_color.setAlpha(int(255 * self.transparency / 100))
                self.text_edit.setStyleSheet(self.get_style_sheet())

            except Exception as e:
                self.show_error_message(f"加载配置失败: {str(e)}")
                # 配置文件损坏，删除之
                os.remove(self.config_path)

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(f"transparency={self.transparency}\n")
                f.write(f"window_width={self.width()}\n")
                f.write(f"window_height={self.height()}\n")
                f.write(f"window_x={self.x()}\n")
                f.write(f"window_y={self.y()}\n")
                if self.font:
                    f.write(f"font={self.font.family()}\n")
                    f.write(f"font_size={self.font.pointSize()}\n")
                f.write(f"text_color={self.text_color.name()}\n")
                f.write(f"bg_color={self.bg_color.name()}\n")
        except Exception as e:
            self.show_error_message(f"保存配置失败: {str(e)}")

    def load_recent_file(self):
        """加载最近打开的文件"""
        if os.path.exists(self.recent_file_path):
            try:
                with open(self.recent_file_path, 'r', encoding='utf-8') as file:
                    recent_file = file.readline().strip()
                    if recent_file and os.path.exists(recent_file) and os.path.isfile(recent_file):
                        self.current_file = recent_file
                        self.load_file(recent_file)
                        self.extract_chapters(recent_file)
            except Exception as e:
                self.show_error_message(f"加载最近文件失败: {str(e)}")
                # 尝试删除损坏的最近文件记录
                if os.path.exists(self.recent_file_path):
                    os.remove(self.recent_file_path)

    def save_recent_file(self, file_path):
        """保存最近打开的文件路径"""
        try:
            with open(self.recent_file_path, 'w', encoding='utf-8') as file:
                file.write(file_path)
        except Exception as e:
            self.show_error_message(f"保存最近文件失败: {str(e)}")

    def load_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                self.text_edit.setText(content)
                self.update_empty_state()
                self.hide_timer.start(self.hide_delay)
        except Exception as e:
            self.show_error_message(f"加载文件失败: {str(e)}")
            # 记录详细错误信息
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.datetime.now()}] 加载文件失败: {str(e)}\n")

    def open_file_from_tray(self):
        """从托盘菜单选择文件"""
        self.show_window_from_tray()  # 先显示窗口
        self.open_file()  # 打开文件选择对话框

    def open_file(self):
        """打开文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文本文件",
            os.path.expanduser("~"),
            "文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            self.load_file(file_path)
            self.current_file = file_path
            self.save_recent_file(file_path)
            self.extract_chapters(file_path)

    def extract_chapters(self, file_path):
        """提取章节信息"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                chapter_patterns = [r"第(.*?)章", r"第(.*?)回", r"第(.*?)集", r"第(.*?)卷"]
                chapters = []

                for pattern in chapter_patterns:
                    matches = re.findall(pattern, content)
                    chapters.extend([f"第{match}章" for match in matches if len(match) < 10])

                # 去重并排序
                chapters = list(set(chapters))
                chapters.sort()
                self.chapters = chapters[:20]  # 限制最多20个章节

        except Exception as e:
            self.show_error_message(f"提取章节失败: {str(e)}")

    # 同时添加必要的辅助方法
    def show_error_message(self, message):
        """显示错误消息"""
        msg_box = QMessageBox()
        msg_box.setText(message)
        msg_box.setWindowTitle("错误")
        msg_box.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        msg_box.setAttribute(Qt.WA_TranslucentBackground)
        msg_box.setStyleSheet("background-color: rgba(255, 255, 255, 200); color: black;")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def show_message(self, title, message):
        """显示普通消息"""
        msg_box = QMessageBox()
        msg_box.setText(message)
        msg_box.setWindowTitle(title)
        msg_box.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        msg_box.setAttribute(Qt.WA_TranslucentBackground)
        msg_box.setStyleSheet("background-color: rgba(255, 255, 255, 200); color: black;")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def update_tray_status(self):
        """更新托盘状态显示"""
        if self.is_hidden:
            status = "已隐藏"
        elif self.is_empty:
            status = "等待文件"
        else:
            status = "正在阅读"

        self.status_action.setText(f"状态: {status}")
        self.tray_icon.setToolTip(f"文本阅读器 - {status}")

    def force_show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.is_hidden = False
        self.update_tray_status()

    # 其他方法（open_file, load_file, add_bookmark等）保持不变
    def handle_exception(exc_type, exc_value, exc_traceback):
        """全局异常处理"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = f"程序发生错误: {exc_type.__name__}: {exc_value}"
        print(error_msg)

        # 显示错误消息到托盘
        if 'ex' in globals() and hasattr(globals()['ex'], 'tray_icon'):
            globals()['ex'].tray_icon.showMessage(
                "程序错误",
                f"发生错误，已记录日志\n{exc_type.__name__}",
                QSystemTrayIcon.Critical,
                5000
            )

        # 记录错误日志
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.datetime.now()}] {error_msg}\n")

    # 设置全局异常钩子
    sys.excepthook = handle_exception

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 确保中文显示正常
    font = app.font()
    font.setFamily("SimHei")
    app.setFont(font)

    # 支持应急模式
    emergency_mode = len(sys.argv) > 1 and sys.argv[1] == "--emergency"
    ex = TextReader()

    if emergency_mode:
        ex.transparency = 80
        ex.bg_color.setAlpha(204)
        ex.force_show_window()
        ex.show_message("应急模式", "已重置为默认显示设置")

    sys.exit(app.exec_())