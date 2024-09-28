import os
import io
import json
import re
import time
import zipfile
from PIL import Image, ImageDraw, ImageFont
import requests
import sqlite3
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from customtkinter import ThemeManager
from customtkinter import CTkToplevel, CTkScrollableFrame, CTkLabel, CTkEntry, CTkTextbox, CTkButton
import subprocess
import threading
import tkinter as tk
import send2trash
import ctypes

# 전역 변수 설정
JPG_WIDTH = 165
JPG_HEIGHT = 220
JPG_QUALITY = 90

ROOT_DIR = ""
COVER_DIR = ""
ImgViewerPath = ""
DB_PATH = "hitomi.db"
STAR_IMAGE_PATH = "ratestar.png"  # Make sure this image is in the same directory as your script

def load_settings():
    if os.path.exists('settings.txt'):
        with open('settings.txt', 'r') as f:
            return json.load(f)
    return None

def save_settings(settings):
    with open('settings.txt', 'w') as f:
        json.dump(settings, f)

def get_directory_input(prompt):
    while True:
        path = input(prompt)
        if os.path.isdir(path):
            return path
        print("유효한 디렉토리가 아닙니다. 다시 시도해주세요.")

def get_exe_input(prompt):
    while True:
        path = input(prompt)
        if os.path.isfile(path) and path.lower().endswith('.exe'):
            return path
        print("유효한 .exe 파일이 아닙니다. 다시 시도해주세요.")

def get_dpi_scale():
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    return user32.GetDpiForSystem() / 96.0

def create_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS files
                 (id_hitomi INTEGER PRIMARY KEY, filename TEXT, path TEXT, 
                 title TEXT, artist TEXT, tags TEXT, groups_ TEXT, 
                 series TEXT, characters TEXT, language TEXT, rate INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def json_parser(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return json.loads(response.text[18:])
    except Exception as e:
        print(f"Error parsing JSON: {e}")
    return {}

def get_substring_by_string(text):
    matches = re.findall(r'\(([^)\D]*)\)', text)
    if matches:
        return matches[-1]
    return "0"

def multi_tag_string(obj, tag):
    if obj is None or not isinstance(obj, list):
        return ""
    return ",".join([item.get(tag, "") for item in obj if isinstance(item, dict)])

def insert_query(obj, file):
    return (
        get_substring_by_string(os.path.basename(file)),
        os.path.basename(file),  # 여기서 .replace("'", "''") 제거
        os.path.dirname(file),
        obj.get('title', ''),  # 여기서도 .replace("'", "''") 제거
        multi_tag_string(obj.get('artists'), 'artist'),
        multi_tag_string(obj.get('tags'), 'tag'),
        multi_tag_string(obj.get('groups'), 'group'),
        multi_tag_string(obj.get('parodys'), 'parody'),
        multi_tag_string(obj.get('characters'), 'character'),
        obj.get('language_localname', '')
    )

def sql_insert(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO files(id_hitomi, filename, path, title, artist, 
                 tags, groups_, series, characters, language) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
    conn.commit()
    conn.close()

def sql_select_count(file):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT COUNT(*) FROM files WHERE path = ? AND filename = ?''', 
              (os.path.dirname(file), os.path.basename(file)))
    count = c.fetchone()[0]
    conn.close()
    return count

def unzip_img(dir, file):
    with zipfile.ZipFile(file, 'r') as zip_ref:
        for item in zip_ref.namelist():
            if item.lower().endswith(('.jpg', '.png', '.webp', '.gif', '.jpeg')):
                zip_ref.extract(item, dir)
                old_name = os.path.join(dir, item)
                new_name = os.path.join(dir, f"{get_substring_by_string(os.path.basename(file))}.jpg")
                
                if os.path.exists(new_name):
                    os.remove(new_name)
                
                os.rename(old_name, new_name)
                
                if not new_name.lower().endswith('.webp'):
                    convert_to_jpg(new_name)
                else:
                    convert_webp_to_jpg(new_name)
                
                break

def convert_to_jpg(image_path):
    with Image.open(image_path) as img:
        img = img.resize((JPG_WIDTH, JPG_HEIGHT))
        img = img.convert('RGB')
        img.save(image_path, 'JPEG', quality=JPG_QUALITY)

def convert_webp_to_jpg(webp_image_path):
    with Image.open(webp_image_path) as img:
        img = img.resize((JPG_WIDTH, JPG_HEIGHT))
        img = img.convert('RGB')
        jpg_image_path = os.path.splitext(webp_image_path)[0] + '.jpg'
        img.save(jpg_image_path, 'JPEG', quality=JPG_QUALITY)
    os.remove(webp_image_path)

def update_database(self):
    create_db()
    
    zip_files = []
    duplicate_files = []
    error_files = []
    for root, dirs, files in os.walk(ROOT_DIR):
        for file in files:
            if file.endswith('.zip'):
                zip_files.append(os.path.join(root, file))
    
    total_files = len(zip_files)

    for i, full_path in enumerate(zip_files, 1):
        print(f"{i} / {total_files}")
        
        gal_num = get_substring_by_string(os.path.basename(full_path))
        
        try:
            if sql_select_count(full_path) == 0:
                if gal_num != "0":
                    obj = json_parser(f"https://ltn.hitomi.la/galleries/{gal_num}.js")
                else:
                    obj = {}
                
                data = insert_query(obj, full_path)
                sql_insert(data)
                time.sleep(0.2)
                #print(f"[DB]<add> {full_path}")
            else:
                #print(f"[DB]<pass> 이미 존재 {full_path}")
                dummyint = 1
        except sqlite3.IntegrityError as e: #이미 등록된 경우
            if gal_num != "0":
                #duplicate_files.append(str(e) + " : " + full_path + "___(" + gal_num)
                duplicate_files.append(full_path)
            else:
                error_files.append(str(e) + " : " + full_path + "___(" + gal_num)
            continue
        except Exception as e:
            print(f"[DB]<error> DB 처리 중 오류 발생 : {full_path}")
            print(f"  오류 내용: {e}")
            continue
        
        try:
            cover_path = os.path.join(COVER_DIR, f"{gal_num}.jpg")
            if not os.path.exists(cover_path):
                unzip_img(COVER_DIR, full_path)
                #print("ㄴ[IMG]<add> 커버 이미지")
            else:
                #print("ㄴ[IMG]<pass> 커버 이미지")
                dummyint = 1
        except Exception as e:
            print(f"ㄴ<error> 커버 이미지 처리 중 오류 발생 : {full_path}")
            print(f"  오류 내용: {e}")
    
    #print("문제 있었던 파일 리스트")
    if len(duplicate_files) != 0:  # hitomi id 중복 리스트 체크
        duplicateFileDel(self, duplicate_files)
    
    for errors in error_files:
        print(errors)
    print(f"id 없는 파일 갯수 : {len(error_files)}")
    
def duplicateFileDel(master, filelists):
    file_count = len(filelists)
    msg = CTkMessagebox(master=master,
                        title="삭제 확인", 
                        message=f"hitomi id가 중복인 파일 {file_count}개를 삭제하시겠습니까?",
                        icon="question", 
                        option_1="취소", 
                        option_2="확인")
    
    response = msg.get()
    
    if response == "확인":
        for file_path in filelists:
            try:
                #print(f"삭제 대상 경로 정보: {file_path}")
                send2trash.send2trash(file_path)
                print(f"Deleted: {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
    
class AutocompleteComboBox(ctk.CTkComboBox):
    def __init__(self, master, completevalues=None, field_name='artist', **kwargs):
        if completevalues is None:
            completevalues = []
        self.field_name = field_name
        super().__init__(master, values=completevalues, **kwargs)
        self.completevalues = completevalues
        self._entry.bind('<KeyRelease>', self.handle_keyrelease)
        self._entry.bind('<FocusOut>', self.handle_focus_out)
        self._entry.bind('<FocusOut>', self.close_dropdown)
        self._create_dropdown()
        self._dropdown_window.geometry(f"{self.winfo_width()}x200")  # 드롭다운 창의 크기 설정

        self.debounce_after = None
        self.max_items = 100  # 표시할 최대 항목 수
        self.min_chars = 2  # 검색을 시작할 최소 문자 수
        
        # 새로운 키 바인딩 추가
        self._entry.bind('<Down>', self.handle_down)
        self._entry.bind('<Up>', self.handle_up)
        self._entry.bind('<Right>', self.handle_right)

        self.current_selection = -1  # 현재 선택된 아이템의 인덱스

    def _create_dropdown(self):
        self._dropdown_window = ctk.CTkToplevel(self)
        self._dropdown_window.withdraw()
        self._dropdown_window.overrideredirect(True)
        self._dropdown_list = ctk.CTkScrollableFrame(self._dropdown_window)
        self._dropdown_list.pack(expand=True, fill="both")
        self._dropdown_window.bind('<FocusOut>', self.handle_focus_out)

    def handle_keyrelease(self, event):
        if event.keysym in ['Down', 'Up', 'Right']:
            return
        
        if self.debounce_after:
            self.after_cancel(self.debounce_after)
        
        self.debounce_after = self.after(300, self.delayed_search)
        
        # 입력 포커스 유지
        self._entry.focus_set()

    def delayed_search(self):
        value = self._entry.get().lower()
        if len(value) < self.min_chars:
            self._close_dropdown()
            return

        threading.Thread(target=self.search_values, args=(value,)).start()

    def search_values(self, value):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute(f'''SELECT DISTINCT {self.field_name} FROM files 
                     WHERE {self.field_name} LIKE ? 
                     ORDER BY {self.field_name} 
                     LIMIT ?''', (f'{value}%', self.max_items))
        
        data = [row[0] for row in c.fetchall() if row[0]]  # 빈 문자열 제외
        conn.close()

        self.after(0, lambda: self.update_dropdown(data))

    def update_dropdown(self, data):
        self.configure(values=data)
        if data:
            self._open_dropdown()
        else:
            self._close_dropdown()

    def handle_focus_out(self, event):
        # 포커스가 드롭다운 창으로 이동한 경우에는 닫지 않음
        if not self._dropdown_window.focus_get():
            self.after(100, self.close_dropdown)

    def set_completevalues(self, values):
        self.completevalues = values

    def _open_dropdown(self):
        if not self._dropdown_window.winfo_viewable():
            self._dropdown_window.deiconify()
            self._dropdown_window.geometry(f"{self.winfo_width()}x200+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        self._update_dropdown_list()
        self._dropdown_window.lift()
        
        # 드롭다운이 열린 후에도 입력 포커스 유지
        self._entry.focus_set()

    def _update_dropdown_list(self):
        for widget in self._dropdown_list.winfo_children():
            widget.destroy()
        
        for value in self.cget("values"):
            btn = self.create_scrolling_button(self._dropdown_list, value, lambda v=value: self._select_value(v))
            btn.pack(fill="x", padx=2, pady=1)
            btn.bind("<Enter>", lambda e, b=btn: self.start_scrolling(b))
            btn.bind("<Leave>", lambda e, b=btn: self.stop_scrolling(b))

    def _select_value(self, value):
        self.set(value)
        self._close_dropdown()

    def _close_dropdown(self):
        if self._dropdown_window.winfo_viewable():
            self._dropdown_window.withdraw()
        self.current_selection = -1

    def handle_down(self, event):
        if self._dropdown_window.winfo_viewable():
            children = self._dropdown_list.winfo_children()
            if children:
                self.current_selection = (self.current_selection + 1) % len(children)
                self._highlight_selection()
        return "break"  # 이벤트 전파 중단

    def handle_up(self, event):
        if self._dropdown_window.winfo_viewable():
            children = self._dropdown_list.winfo_children()
            if children:
                self.current_selection = (self.current_selection - 1) % len(children)
                self._highlight_selection()
        return "break"  # 이벤트 전파 중단

    def handle_right(self, event):
        if self._dropdown_window.winfo_viewable():
            children = self._dropdown_list.winfo_children()
            if children and 0 <= self.current_selection < len(children):
                self._select_value(children[self.current_selection].cget("text"))
        return "break"  # 이벤트 전파 중단

    def _highlight_selection(self):
        children = self._dropdown_list.winfo_children()
        for i, child in enumerate(children):
            if i == self.current_selection:
                child.configure(fg_color="blue")  # 선택된 아이템 강조
                self.start_scrolling(child)
            else:
                child.configure(fg_color=ThemeManager.theme["CTkButton"]["fg_color"])
                self.stop_scrolling(child)
        
        # 선택된 아이템이 보이도록 스크롤
        if self.current_selection >= 0:
            self._dropdown_list._parent_canvas.yview_moveto(
                self.current_selection / len(children)
            )
            
    def close_dropdown(self, event=None):
        if self._dropdown_window.winfo_viewable():
            self._dropdown_window.withdraw()
        self.current_selection = -1
        
    def create_scrolling_button(self, master, text, command):
        button = ctk.CTkButton(master, text=text, anchor="w", command=command)
        button.original_text = text
        button.scrolling = False
        return button
    
    def start_scrolling(self, button):
        if len(button.original_text) * 7 > button.winfo_width():  # 대략적인 글자 너비 계산
            button.scrolling = True
            self.scroll_text(button, 0)
    
    def stop_scrolling(self, button):
        button.scrolling = False
        button.configure(text=button.original_text)
    
    def scroll_text(self, button, index):
        if not button.scrolling:
            return
        text = button.original_text
        display_text = text[index:] + "   " + text[:index]
        button.configure(text=display_text)
        next_index = (index + 1) % len(text)
        button.after(100, lambda: self.scroll_text(button, next_index))


class AutocompleteEntry(ctk.CTkEntry):
    def __init__(self, autocompleteList, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autocompleteList = autocompleteList
        self.var = ctk.StringVar()
        self.configure(textvariable=self.var)
        self.var.trace('w', self.changed)
        self.bind("<Right>", self.selection)
        self.bind("<Up>", self.up)
        self.bind("<Down>", self.down)
        
        self.listboxUp = False
        self.listbox = None

    def changed(self, name, index, mode):
        if self.var.get() == '':
            if self.listboxUp:
                self.listbox.destroy()
                self.listboxUp = False
        else:
            words = self.comparison()
            if words:
                if not self.listboxUp:
                    self.listbox = ctk.CTkFrame(self, width=self.winfo_width())
                    self.listbox.place(x=0, y=self.winfo_height())
                    self.listboxUp = True

                for widget in self.listbox.winfo_children():
                    widget.destroy()

                for word in words:
                    button = ctk.CTkButton(self.listbox, text=word, command=lambda w=word: self.selection_from_listbox(w))
                    button.pack(fill='x')
            else:
                if self.listboxUp:
                    self.listbox.destroy()
                    self.listboxUp = False


    def selection_from_listbox(self, word):
        self.var.set(word)
        self.listbox.destroy()
        self.listboxUp = False
        self.icursor(ctk.END)

    def selection(self, event):
        if self.listboxUp:
            widgets = self.listbox.winfo_children()
            if widgets:
                self.var.set(widgets[0].cget("text"))
                self.listbox.destroy()
                self.listboxUp = False
                self.icursor(ctk.END)

    def up(self, event):
        if self.listboxUp:
            widgets = self.listbox.winfo_children()
            if widgets:
                active_index = None
                for index, widget in enumerate(widgets):
                    if widget.cget("fg_color") == "blue":
                        active_index = index
                        break
                
                if active_index is None:
                    active_index = 0
                else:
                    widgets[active_index].configure(fg_color="")

                if active_index > 0:
                    active_index -= 1
                
                widgets[active_index].configure(fg_color="blue")

    def down(self, event):
        if self.listboxUp:
            widgets = self.listbox.winfo_children()
            if widgets:
                active_index = None
                for index, widget in enumerate(widgets):
                    if widget.cget("fg_color") == "blue":
                        active_index = index
                        break
                
                if active_index is None:
                    active_index = -1
                else:
                    widgets[active_index].configure(fg_color="")

                if active_index < len(widgets) - 1:
                    active_index += 1
                
                widgets[active_index].configure(fg_color="blue")

    def comparison(self):
        pattern = self.var.get().lower()
        return [w for w in self.autocompleteList if w.lower().startswith(pattern)]

class HitomiGalleryApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Hitomi Gallery")
        self.geometry("1200x700")
        self.resize_timer = None
        
        # 설정 로드
        self.settings = load_settings()
        if self.settings is None:
            self.get_settings_from_user()
        else:
            self.ROOT_DIR = self.settings['ROOT_DIR']
            self.COVER_DIR = self.settings['COVER_DIR']
            self.ImgViewerPath = self.settings['ImgViewerPath']

        # 검색 프레임
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.pack(padx=10, pady=10, fill="x")

        # 첫 번째 줄: Title, Series, Artist, Groups
        self.first_row = ctk.CTkFrame(self.search_frame)
        self.first_row.pack(fill="x", padx=5, pady=5)

        self.title_label = ctk.CTkLabel(self.first_row, text="Title:")
        self.title_label.pack(side="left", padx=5)
        self.title_entry = ctk.CTkEntry(self.first_row, width=200)
        self.title_entry.pack(side="left", padx=5)
        self.title_entry.bind('<Return>', self.search)

        self.artist_var = ctk.StringVar()
        self.artist_label = ctk.CTkLabel(self.first_row, text="artist:")
        self.artist_label.pack(side="left", padx=5)
        self.artist_dropdown = AutocompleteComboBox(self.first_row, variable=self.artist_var, field_name='artist')
        self.artist_dropdown.pack(side="left", padx=5)
        self.artist_dropdown.bind('<Return>', self.search)
        self.artist_dropdown._entry.bind('<FocusIn>', lambda e: self.close_other_dropdowns(self.artist_dropdown))
        
        self.series_var = ctk.StringVar()
        self.series_label = ctk.CTkLabel(self.first_row, text="series:")
        self.series_label.pack(side="left", padx=5)
        self.series_dropdown = AutocompleteComboBox(self.first_row, variable=self.series_var, field_name='series')
        self.series_dropdown.pack(side="left", padx=5)
        self.series_dropdown.bind('<Return>', self.search)
        self.series_dropdown._entry.bind('<FocusIn>', lambda e: self.close_other_dropdowns(self.series_dropdown))

        self.groups_var = ctk.StringVar()
        self.groups_label = ctk.CTkLabel(self.first_row, text="groups:")
        self.groups_label.pack(side="left", padx=5)
        self.groups_dropdown = AutocompleteComboBox(self.first_row, variable=self.groups_var, field_name='groups_')
        self.groups_dropdown.pack(side="left", padx=5)
        self.groups_dropdown.bind('<Return>', self.search)
        self.groups_dropdown._entry.bind('<FocusIn>', lambda e: self.close_other_dropdowns(self.groups_dropdown))

        self.characters_var = ctk.StringVar()
        self.characters_label = ctk.CTkLabel(self.first_row, text="characters:")
        self.characters_label.pack(side="left", padx=5)
        self.characters_dropdown = AutocompleteComboBox(self.first_row, variable=self.characters_var, field_name='characters')
        self.characters_dropdown.pack(side="left", padx=5)
        self.characters_dropdown.bind('<Return>', self.search)
        self.characters_dropdown._entry.bind('<FocusIn>', lambda e: self.close_other_dropdowns(self.characters_dropdown))
        
        # 두 번째 줄: Tags, Search, Update
        self.second_row = ctk.CTkFrame(self.search_frame)
        self.second_row.pack(fill="x", padx=5, pady=5)

        self.tags_label = ctk.CTkLabel(self.second_row, text="Tags:")
        self.tags_label.pack(side="left", padx=5)
        self.tags_var = tk.StringVar()
        self.tags_entry = ctk.CTkEntry(self.second_row, width=750, textvariable=self.tags_var)
        self.tags_entry.pack(side="left", padx=5)
        self.tags_entry.bind('<KeyRelease>', self.on_key_release)
        self.tags_entry.bind('<Down>', self.on_up_down_key)
        self.tags_entry.bind('<Up>', self.on_up_down_key)
        self.tags_entry.bind('<Right>', self.on_select)
        self.tags_entry.bind('<Return>', self.search, add='+')

        self.search_button = ctk.CTkButton(self.second_row, text="Search", width=70,command=self.search)
        self.search_button.pack(side="left", padx=5)

        self.update_button = ctk.CTkButton(self.second_row, text="Update", width=70,command=self.update)
        self.update_button.pack(side="left", padx=5)

        # 세 번째 줄: Previous, Next, Page Size
        self.third_row = ctk.CTkFrame(self.search_frame)
        self.third_row.pack(fill="x", padx=5, pady=5)

        self.prev_button = ctk.CTkButton(self.third_row, text="Previous", width=70,command=self.prev_page)
        self.prev_button.pack(side="left", padx=5)

        self.next_button = ctk.CTkButton(self.third_row, text="Next", width=70,command=self.next_page)
        self.next_button.pack(side="left", padx=5)

        # 정렬 옵션 추가
        self.rate_label = ctk.CTkLabel(self.third_row, text="Rate:")
        self.rate_label.pack(side="left", padx=5)
        self.rate_var = ctk.StringVar()
        self.rate_dropdown = ctk.CTkOptionMenu(self.third_row, variable=self.rate_var, width=50,
                                               values=["All", "1", "2", "3", "4", "5"], 
                                               command=self.search)
        self.rate_dropdown.pack(side="left", padx=5)
        self.rate_dropdown.set("All")
        
        self.sort_label = ctk.CTkLabel(self.third_row, text="Sort:")
        self.sort_label.pack(side="left", padx=5)
        self.sort_var = ctk.StringVar(value="DESC")
        self.sort_dropdown = ctk.CTkOptionMenu(self.third_row, variable=self.sort_var, 
                                            values=["DESC", "ASC", "RANDOM"], width=100,
                                            command=self.search)
        self.sort_dropdown.pack(side="left", padx=5)

        self.page_size_label = ctk.CTkLabel(self.third_row, text="Page Size:")
        self.page_size_label.pack(side="left", padx=5)
        self.page_size_var = ctk.IntVar(value=20)
        self.page_size_dropdown = ctk.CTkOptionMenu(self.third_row, variable=self.page_size_var, values=["20", "50", "100"], width=70,command=self.update_page_size)
        self.page_size_dropdown.pack(side="left", padx=5)

        self.current_page_label = ctk.CTkLabel(self.third_row, text="Current Page:")
        self.current_page_label.pack(side="left", padx=5)
        self.current_page_var = ctk.StringVar(value="1")
        self.current_page_entry = ctk.CTkEntry(self.third_row, width=50, textvariable=self.current_page_var)
        self.current_page_entry.pack(side="left", padx=5)
        self.current_page_entry.bind('<Return>', self.update_current_page)

        self.total_pages_label = ctk.CTkLabel(self.third_row, text="/ 1")
        self.total_pages_label.pack(side="left", padx=5)

        # 태그 자동완성을 위한 리스트박스
        self.tags_frame = tk.Frame(self)
        self.tags_scrollbar = tk.Scrollbar(self.tags_frame, orient="vertical")
        self.tags_listbox = tk.Listbox(self.tags_frame, yscrollcommand=self.tags_scrollbar.set, 
                                       bg=ctk.ThemeManager.theme["CTkFrame"]["fg_color"][1], 
                                       fg="white", selectbackground="gray")
        self.tags_scrollbar.config(command=self.tags_listbox.yview)
        self.tags_scrollbar.pack_forget()
        self.tags_listbox.pack(side="left", fill="both", expand=True)
        self.tags_frame.place_forget()

        self.tags_listbox.bind('<<ListboxSelect>>', self.on_select)

        # 결과 프레임
        self.result_frame = ctk.CTkScrollableFrame(self)
        self.result_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.image_buttons = []
        
        # 현재 페이지 및 검색 결과
        self.current_page = 1
        self.total_pages = 1
        self.results = []

        # 태그 리스트
        self.tags_list = []

        # 최초실행시 db가 생성되어 있지않다면 갱신 시작
        if not os.path.exists(DB_PATH):
            update_database(self)

        # 드롭다운 옵션 초기화
        self.initialize_dropdowns()
        
        self.selected_image = None
        self.star_image = Image.open(STAR_IMAGE_PATH).resize((20, 20))  # Adjust size as needed

        # Bind key press event to the whole application
        self.bind("<Key>", self.set_rating)
        self.bind("<Key>", self.on_key_press)
        
        # Bind delete key press event to the whole application
        self.bind("<Delete>", self.confirm_delete)
        
        
        # 현재 열 수를 저장할 변수
        self.current_columns = 5
        
        self.search()
        
        # 창 크기 변경 이벤트 바인딩
        self.resizing = False
        self.bind('<ButtonPress-1>', self.on_resize_start)
        self.bind('<ButtonRelease-1>', self.on_resize_end)
        
        self.after(100, self.initial_layout)
        
        self.dpi_scale = get_dpi_scale()
        self.scaled_width = int(JPG_WIDTH * self.dpi_scale)
        self.scaled_height = int(JPG_HEIGHT * self.dpi_scale)
        
        self.selected_button = None  # 선택된 버튼을 추적하기 위한 변수 추가

    def on_key_press(self, event):
        if event.char == 'i' and self.selected_image is not None and self.focus_get() == self:
            self.show_image_info(self.selected_image)
        elif event.char == 'c' and self.selected_image is not None and self.focus_get() == self:
            self.change_cover_image(self.selected_image)
    
    def change_cover_image(self, id_hitomi):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT path, filename FROM files WHERE id_hitomi = ?', (id_hitomi,))
        result = c.fetchone()
        conn.close()

        if result:
            path, filename = result
            full_path = os.path.join(path, filename)
            if os.path.exists(full_path):
                self.show_cover_selection(full_path, id_hitomi)
            else:
                print(f"파일을 찾을 수 없습니다: {full_path}")
        else:
            print(f"id_hitomi에 해당하는 파일을 찾을 수 없습니다: {id_hitomi}")


    def show_cover_selection(self, zip_path, id_hitomi):
        preview_window = ctk.CTkToplevel(self)
        preview_window.title("커버 이미지 선택")
        preview_window.geometry("900x250")

        # DPI 스케일 가져오기
        dpi_scale = self.dpi_scale  # 이미 클래스에서 정의된 DPI 스케일 사용

        # 창을 화면 중앙에 위치시키는 코드
        preview_window.update_idletasks()  # 창 크기 업데이트
        width = preview_window.winfo_width()
        height = preview_window.winfo_height()
        screen_width = preview_window.winfo_screenwidth() / dpi_scale
        screen_height = preview_window.winfo_screenheight() / dpi_scale
        x = int((screen_width - width) // 2 * dpi_scale)
        y = int((screen_height - height) // 2 * dpi_scale)
        preview_window.geometry(f'+{x}+{y}')

        preview_frame = ctk.CTkFrame(preview_window)
        preview_frame.pack(expand=True, fill="both", padx=10, pady=10)

        image_buttons = []
        selected_image = [None]

        # DPI 스케일을 고려한 이미지 크기 계산
        scaled_width = int(100 * self.dpi_scale)
        scaled_height = int(100 * self.dpi_scale)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            image_files = [f for f in zip_ref.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
            preview_images = image_files[:5]  # 처음 5개의 이미지만 선택

            for i, image_file in enumerate(preview_images):
                with zip_ref.open(image_file) as file:
                    img_data = file.read()
                    img = Image.open(io.BytesIO(img_data))
                    img = img.convert('RGB')  # webp 이미지를 RGB로 변환
                    img.thumbnail((scaled_width, scaled_height))  # 썸네일 크기 조정
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=(scaled_width, scaled_height))

                    def select_image(img_file=image_file):
                        selected_image[0] = img_file
                        for btn in image_buttons:
                            btn.configure(border_width=0)
                        image_buttons[i].configure(border_width=2, border_color="blue")

                    button = ctk.CTkButton(preview_frame, image=photo, text="", width=scaled_width, height=scaled_height, command=select_image)
                    button.grid(row=0, column=i, padx=5, pady=5)
                    image_buttons.append(button)

        def confirm_selection():
            if selected_image[0]:
                self.update_cover_image(zip_path, selected_image[0], id_hitomi)
                preview_window.destroy()

        confirm_button = ctk.CTkButton(preview_window, text="확인", command=confirm_selection)
        confirm_button.pack(pady=10)
        
        # 창이 완전히 생성된 후 포커스를 설정하고 맨 앞으로 가져오기
        self.after(100, lambda: self.bring_window_to_front(preview_window))

        # ESC 키 바인딩 추가
        preview_window.bind('<Escape>', lambda e: preview_window.destroy())


    def bring_window_to_front(self, window):
        window.lift()
        window.focus_force()
        window.grab_set()
        window.grab_release()

    def update_cover_image(self, zip_path, selected_image, id_hitomi):
        cover_path = os.path.join(COVER_DIR, f"{id_hitomi}.jpg")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            with zip_ref.open(selected_image) as file:
                img_data = file.read()
                img = Image.open(io.BytesIO(img_data))
                img = img.convert('RGB')
                img.thumbnail((JPG_WIDTH, JPG_HEIGHT))
                img.save(cover_path, 'JPEG', quality=JPG_QUALITY)

        print(f"커버 이미지가 업데이트되었습니다: {cover_path}")
        self.search(maintain_page=True)  # 현재 페이지 유지하며 검색 결과 새로고침


    def show_image_info(self, id_hitomi):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT id_hitomi, filename, path, title, artist, tags, groups_, series, characters, rate 
                    FROM files WHERE id_hitomi = ?''', (id_hitomi,))
        result = c.fetchone()
        conn.close()
    
        if result:
            info_window = CTkToplevel(self)
            info_window.title(f"Image Info - Hitomi ID: {id_hitomi}")
            info_window.geometry("500x500")

            # DPI 스케일 가져오기
            dpi_scale = self.dpi_scale

            # 창을 화면 중앙에 위치시키는 코드
            info_window.update_idletasks()  # 창 크기 업데이트
            width = info_window.winfo_width()
            height = info_window.winfo_height()
            screen_width = info_window.winfo_screenwidth() / dpi_scale
            screen_height = info_window.winfo_screenheight() / dpi_scale
            x = int((screen_width - width) // 2 * dpi_scale)
            y = int((screen_height - height) // 2 * dpi_scale)
            info_window.geometry(f'+{x}+{y}')
    
            info_frame = CTkScrollableFrame(info_window)
            info_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
            labels = ["ID Hitomi", "Filename", "Path", "Title", "Artist", "Tags", "Groups", "Series", "Characters", "Rate"]
            entries = {}
    
            for i, (label, value) in enumerate(zip(labels, result)):
                CTkLabel(info_frame, text=f"{label}:", anchor="w", font=("Arial", 12, "bold")).grid(row=i, column=0, sticky="w", pady=2)
                if label in ["Artist", "Tags", "Groups", "Series", "Characters"]:
                    if label in ["Tags", "Characters"]:
                        entry = CTkTextbox(info_frame, height=60, wrap="word")
                        entry.insert("1.0", value)
                    else:
                        entry = CTkEntry(info_frame, width=300)
                        entry.insert(0, value)
                    entry.grid(row=i, column=1, sticky="ew", pady=2)
                    entries[label.lower()] = entry
                else:
                    CTkLabel(info_frame, text=str(value), anchor="w", wraplength=300).grid(row=i, column=1, sticky="w", pady=2)
    
            info_frame.grid_columnconfigure(1, weight=1)
    
            # 업데이트 버튼 추가
            update_button = CTkButton(info_window, text="Update", command=lambda: self.update_image_info(id_hitomi, entries))
            update_button.pack(pady=10)
    
            # 창이 완전히 생성된 후 포커스를 설정하고 맨 앞으로 가져오기
            self.after(100, lambda: self.bring_window_to_front(info_window))
    
            # 창이 닫힐 때 원래 창으로 포커스 돌려주기
            def on_closing():
                self.focus_force()
                self.selected_image = None
                self.selected_button = None
                info_window.destroy()
    
            info_window.protocol("WM_DELETE_WINDOW", on_closing)
    
            # ESC 키 바인딩 추가
            info_window.bind('<Escape>', lambda e: on_closing())
            # 'C' 키 바인딩 추가
            self.bind("<Key>", self.on_key_press)


    def update_image_info(self, id_hitomi, entries):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        update_query = '''UPDATE files SET 
                          artist = ?, tags = ?, groups_ = ?, series = ?, characters = ?
                          WHERE id_hitomi = ?'''
        
        artist = entries['artist'].get()
        tags = entries['tags'].get("1.0", "end-1c")  # CTkTextbox에서 텍스트 가져오기
        groups = entries['groups'].get()
        series = entries['series'].get()
        characters = entries['characters'].get("1.0", "end-1c")  # CTkTextbox에서 텍스트 가져오기
        
        c.execute(update_query, (artist, tags, groups, series, characters, id_hitomi))
        conn.commit()
        conn.close()
        
        print(f"Updated info for image {id_hitomi}")
        self.search(maintain_page=True)  # 현재 페이지 유지하며 검색 결과 새로고침

    def bring_window_to_front(self, window):
        window.lift()
        window.focus_force()
        window.grab_set()
        window.grab_release()
    
    def initial_layout(self):
        self.current_columns = self.calculate_columns()
        self.display_results()
        self.result_frame._parent_canvas.yview_moveto(0)  # 스크롤을 최상단으로 이동
        self.bind('<Configure>', self.on_window_resize)
    
    def get_settings_from_user(self):
        self.ROOT_DIR = get_directory_input("히토미 갤러리 루트 디렉토리를 입력하세요: ")
        self.COVER_DIR = get_directory_input("커버 이미지 디렉토리를 입력하세요: ")
        self.ImgViewerPath = get_exe_input("이미지 뷰어(.exe) 경로를 입력하세요: ")
        
        self.settings = {
            'ROOT_DIR': self.ROOT_DIR,
            'COVER_DIR': self.COVER_DIR,
            'ImgViewerPath': self.ImgViewerPath
        }
        save_settings(self.settings)
    
    def on_resize_start(self, event):
        if self.winfo_width() - event.x < 10 or self.winfo_height() - event.y < 10:
            self.resizing = True
    
    def on_resize_end(self, event):
        if self.resizing:
            self.resizing = False
            self.after(100, self.delayed_resize)  # 약간의 지연을 줍니다.
    
    def on_window_resize(self, event):
        if event.widget == self:
            if self.resize_timer is not None:
                self.after_cancel(self.resize_timer)
            self.resize_timer = self.after(300, self.delayed_resize)
    
    def delayed_resize(self):
        new_columns = self.calculate_columns()
        if new_columns != self.current_columns:
            self.current_columns = new_columns
            self.display_results()
        self.resize_timer = None

    def calculate_columns(self):
        window_width = self.result_frame.winfo_width()
        padding = int(10*self.dpi_scale)  # 이미지 사이의 패딩
        #columns = max(1, (window_width - padding) // (JPG_WIDTH + padding))
        columns = max(1, (window_width)//(self.scaled_width + (padding*2)))
        #print(columns)
        return columns

    def initialize_dropdowns(self):
        # 모든 드롭다운의 completevalues를 빈 리스트로 초기화
        self.artist_dropdown.set_completevalues([])
        self.series_dropdown.set_completevalues([])
        self.groups_dropdown.set_completevalues([])
        self.characters_dropdown.set_completevalues([])

        # Tags 옵션 (이 부분은 변경하지 않음)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT DISTINCT tags FROM files WHERE tags != ''")
        self.tags_list = list(set(tag.strip() for row in c.fetchall() for tag in row[0].split(',')))
        conn.close()

    def close_other_dropdowns(self, current_dropdown):
        dropdowns = [self.artist_dropdown, self.series_dropdown, self.groups_dropdown, self.characters_dropdown]
        for dropdown in dropdowns:
            if dropdown != current_dropdown:
                dropdown.close_dropdown()

    def confirm_delete(self, event):
        if self.selected_image is not None:
            msg = CTkMessagebox(master=self,  # 부모 윈도우 지정
                                title="삭제 확인", 
                                message="선택한 이미지를 삭제하시겠습니까?",
                                icon="question", 
                                option_1="취소", 
                                option_2="확인")
            
            # Enter 키와 Esc 키에 대한 바인딩 추가
            msg.bind("<Return>", lambda event: msg.button_2.invoke())  # '확인' 버튼 클릭
            msg.bind("<Escape>", lambda event: msg.button_1.invoke())  # '취소' 버튼 클릭
            
            # 메시지 박스에 포커스 설정
            msg.focus_set()
            
            # 모달 동작을 위해 grab_set() 사용
            msg.grab_set()
            
            self.wait_window(msg)
            
            response = msg.get()
            
            if response == "확인":
                self.delete_selected_image()

    def delete_selected_image(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get file information
        c.execute('SELECT path, filename FROM files WHERE id_hitomi = ?', (self.selected_image,))
        result = c.fetchone()
        
        if result:
            path, filename = result
            full_path = os.path.join(path, filename)
            cover_path = os.path.join(COVER_DIR, f"{self.selected_image}.jpg")
            
            # Delete from database
            c.execute('DELETE FROM files WHERE id_hitomi = ?', (self.selected_image,))
            conn.commit()
            
            # Move files to trash
            if os.path.exists(full_path):
                send2trash.send2trash(full_path)
            if os.path.exists(cover_path):
                send2trash.send2trash(cover_path)
            
            print(f"Deleted file for id_hitomi: {self.selected_image}")
            
            # Refresh search results
            self.search(maintain_page=True)
        else:
            print(f"No file found for id_hitomi: {self.selected_image}")
        
        conn.close()
        self.selected_image = None

    def on_key_release(self, event):
        if event.keysym in ["Up", "Down"]:
            return
        value = self.tags_var.get().strip().lower().split(',')[-1].strip()
        if value == '':
            self.listbox_update([])
        else:
            data = [item for item in self.tags_list if value in item.lower()]
            self.listbox_update(data)

    def listbox_update(self, data):
        self.tags_listbox.delete(0, 'end')
        for item in data:
            self.tags_listbox.insert('end', item)
        if data:
            height = min(len(data), 10)  # 최대 10개의 항목만 표시
            self.tags_listbox.config(height=height)
            self.tags_frame.place(x=self.tags_entry.winfo_x(), y=self.tags_entry.winfo_y() + self.tags_entry.winfo_height())
        else:
            self.tags_frame.place_forget()

    def on_select(self, event=None):
        if self.tags_listbox.curselection():
            selection = self.tags_listbox.get(self.tags_listbox.curselection())
            current_text = self.tags_var.get()
            new_text = ', '.join(current_text.split(',')[:-1] + [selection])
            self.tags_var.set(new_text + ', ')
            self.tags_frame.place_forget()
            self.tags_entry.icursor(tk.END)  # 커서를 맨 뒤로 이동

    def on_up_down_key(self, event):
        if event.keysym == "Down":
            if self.tags_listbox.curselection() == ():
                self.tags_listbox.selection_set(0)
            else:
                current_selection = self.tags_listbox.curselection()[0]
                self.tags_listbox.selection_clear(current_selection)
                self.tags_listbox.selection_set((current_selection + 1) % self.tags_listbox.size())
            self.tags_listbox.activate(self.tags_listbox.curselection())
            self.tags_listbox.see(self.tags_listbox.curselection())
        elif event.keysym == "Up":
            if self.tags_listbox.curselection() == ():
                self.tags_listbox.selection_set(self.tags_listbox.size() - 1)
            else:
                current_selection = self.tags_listbox.curselection()[0]
                self.tags_listbox.selection_clear(current_selection)
                self.tags_listbox.selection_set((current_selection - 1) % self.tags_listbox.size())
            self.tags_listbox.activate(self.tags_listbox.curselection())
            self.tags_listbox.see(self.tags_listbox.curselection())

    def search(self, event=None, maintain_page=False):
        title = self.title_entry.get()
        artist = self.artist_var.get()
        tags = self.tags_entry.get()
        group = self.groups_var.get()
        series = self.series_var.get()
        rate = self.rate_var.get()
        characters = self.characters_var.get()
    
        self.results = self.search_db(title, artist, tags, group, series, rate, characters)
        self.total_pages = max(1, (len(self.results) + self.page_size_var.get() - 1) // self.page_size_var.get())
        
        if not maintain_page:
            self.current_page = 1  # 페이지를 1로 초기화
            self.current_page_var.set("1")  # 페이지 표시도 1로 설정
    
        self.update_page_display()
        self.display_results(maintain_scroll=maintain_page)

    def update_page_size(self, value):
        self.current_page = 1
        self.current_page_var.set("1")
        self.search()

    def update_page_display(self):
        self.current_page_var.set(str(self.current_page))
        self.total_pages_label.configure(text=f"/ {self.total_pages}")

    def search_db(self, title, artist, tags, group, series, rate, characters):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
    
        query = '''SELECT id_hitomi, title, artist, rate FROM files WHERE 1=1'''
        params = []
    
        if title:
            query += ' AND title LIKE ?'
            params.append(f'%{title}%')
        if artist:
            query += ' AND artist LIKE ?'
            params.append(f'%{artist}%')
        if tags:
            for tag in tags.split(','):
                query += ' AND tags LIKE ?'
                params.append(f'%{tag.strip()}%')
        if group:
            query += ' AND groups_ LIKE ?'
            params.append(f'%{group}%')
        if series:
            query += ' AND series LIKE ?'
            params.append(f'%{series}%')
        if characters:
            query += ' AND characters LIKE ?'
            params.append(f'%{characters}%')
        if rate != "All":
            query += ' AND rate = ?'
            params.append(int(rate))
    
        # 정렬 옵션 적용
        sort_option = self.sort_var.get()
        if sort_option == "DESC":
            query += ' ORDER BY id_hitomi DESC'
        elif sort_option == "ASC":
            query += ' ORDER BY id_hitomi ASC'
        elif sort_option == "RANDOM":
            query += ' ORDER BY RANDOM()'
    
        c.execute(query, params)
        results = c.fetchall()
        conn.close()
        return results

    def display_results(self, maintain_scroll=False):
        for button in self.image_buttons:
            button.destroy()
        self.image_buttons.clear()
    
        if not maintain_scroll:
            # 스크롤을 최상단으로 이동
            self.result_frame._parent_canvas.yview_moveto(0)
    
        # 페이지 결과 표시
        page_size = self.page_size_var.get()
        start = (self.current_page - 1) * page_size
        end = start + page_size
        page_results = self.results[start:end]
        
        for i, (id_hitomi, title, artist, rate) in enumerate(page_results):
            image_path = os.path.join(COVER_DIR, f"{id_hitomi}.jpg")
            if os.path.exists(image_path):
                img = Image.open(image_path)
                try:
                    img = img.resize((JPG_WIDTH, JPG_HEIGHT))
                except Exception as e:
                    print(f"손상된 커버 이미지 파일 : {e}")
                    print("대상 hitomi id - "+str(id_hitomi))
                    img = Image.open("noImage.jpg")
                    img = img.resize((JPG_WIDTH, JPG_HEIGHT))
                #img = img.resize((JPG_WIDTH, JPG_HEIGHT))
                img_with_stars = self.add_rating_stars(img, rate)
                
                photo = ctk.CTkImage(light_image=img_with_stars, dark_image=img_with_stars, size=(JPG_WIDTH, JPG_HEIGHT))
                
                button = ctk.CTkButton(self.result_frame, image=photo, text="", width=JPG_WIDTH, height=JPG_HEIGHT)
                button.image = photo  # 참조 유지
                button.grid(row=i // self.current_columns, column=i % self.current_columns, padx=5, pady=5)
                button.bind("<Double-Button-1>", lambda e, id=id_hitomi: self.open_in_honeyview(id))
                button.bind("<Button-1>", lambda e, id=id_hitomi, btn=button: self.select_image(id, btn))
                
                self.image_buttons.append(button)

        self.update_page_display()

    def add_rating_stars(self, img, rate):
        img_with_stars = img.copy()
        draw = ImageDraw.Draw(img_with_stars)
        for i in range(rate):
            star_position = (i * 22, img.height - 22)  # Adjust position as needed
            img_with_stars.paste(self.star_image, star_position, self.star_image)
        return img_with_stars

    def select_image(self, id_hitomi, button):
        if self.selected_button and self.selected_button.winfo_exists():
            self.selected_button.configure(border_width=0)  # 이전 선택 제거
        self.selected_image = id_hitomi
        self.selected_button = button
        if button.winfo_exists():
            button.configure(border_width=2, border_color="blue")  # 선택된 이미지에 테두리 추가
    
        # 모든 입력 위젯에서 포커스 제거
        for widget in [self.title_entry, self.series_dropdown._entry, self.artist_dropdown._entry, 
                    self.groups_dropdown._entry, self.tags_entry, self.current_page_entry]:
            widget.unbind('<FocusIn>')
    
        # 메인 윈도우에 포커스 설정
        self.focus_set()

    def set_rating(self, event):
        #print(f"Key pressed: {event.char}")  # Debug message
        
        try:
            if self.selected_image is not None and event.char in "012345":
                rate = int(event.char)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('UPDATE files SET rate = ? WHERE id_hitomi = ?', (rate, self.selected_image))
                conn.commit()
                conn.close()
                if rate == 0:
                    print(f"Rating has been reset to 0 for image {self.selected_image}")
                else:
                    print(f"Rate {rate} has been registered for image {self.selected_image}")
                self.search(maintain_page=True)  # 현재 페이지 유지하며 검색 결과 새로고침
        except ValueError:
            pass

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.update_page_display()
            self.display_results()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_page_display()
            self.display_results()
            
    def update_current_page(self, event=None):
        try:
            new_page = int(self.current_page_var.get())
            if 1 <= new_page <= self.total_pages:
                self.current_page = new_page
                self.display_results()
            else:
                self.current_page_var.set(str(self.current_page))
        except ValueError:
            self.current_page_var.set(str(self.current_page))

    def open_in_honeyview(self, id_hitomi):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT path, filename FROM files WHERE id_hitomi = ?', (id_hitomi,))
        result = c.fetchone()
        conn.close()

        if result:
            path, filename = result
            full_path = os.path.join(path, filename)
            if os.path.exists(full_path):
                subprocess.Popen([self.ImgViewerPath, full_path])
            else:
                print(f"File not found: {full_path}")
        else:
            print(f"No file found for id_hitomi: {id_hitomi}")

    def update(self):
        # Disable the update button
        self.update_button.configure(state="disabled")
        
        # Create and start the update thread
        update_thread = threading.Thread(target=self.run_update)
        update_thread.start()

    def run_update(self):
        # Run the update_database function
        update_database(self)
        
        # Re-enable the update button and refresh dropdowns
        self.after(0, lambda: self.update_button.configure(state="normal"))
        self.after(0, self.initialize_dropdowns)

if __name__ == "__main__":
    settings = load_settings()

    if settings is None:
        print("설정 파일이 없습니다. 새로운 설정을 입력해주세요.")
        ROOT_DIR = get_directory_input("히토미 갤러리 루트 디렉토리를 입력하세요: ")
        COVER_DIR = get_directory_input("커버 이미지 디렉토리를 입력하세요: ")
        ImgViewerPath = get_exe_input("이미지 뷰어(.exe) 경로를 입력하세요: ")
        
        settings = {
            'ROOT_DIR': ROOT_DIR,
            'COVER_DIR': COVER_DIR,
            'ImgViewerPath': ImgViewerPath
        }
        save_settings(settings)
    else:
        ROOT_DIR = settings['ROOT_DIR']
        COVER_DIR = settings['COVER_DIR']
        ImgViewerPath = settings['ImgViewerPath']
        
    app = HitomiGalleryApp()
    app.mainloop()
    
    
