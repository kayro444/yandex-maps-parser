import os
import sys
import asyncio
import threading
import json
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from config import CITIES, NICHES, FREELANCE_KEYWORDS
from parsers.yandex_maps import scrape_yandex_maps
from parsers.fl_ru import scrape_fl_ru
from parsers.kwork import scrape_kwork
from exporters.excel import export_to_excel

if sys.platform == "win32":
    import winsound
else:
    winsound = None

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("LEADNEXUS")
        self.geometry("900x800")
        import os
        import sys
        
        def resource_path(relative_path):
            try:
                base_path = sys._MEIPASS
            except Exception:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)
            
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        
        self.grid_columnconfigure(0, weight=1) # Left panel (Controls)
        self.grid_columnconfigure(1, weight=2) # Right panel (Logs)
        self.grid_rowconfigure(0, weight=1)
        
        self.city_vars = {}
        self.niche_vars = {}
        
        self.settings_file = Path("settings.json")
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        # LEFT PANEL (Controls)
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)
        
        # TABVIEW FOR MODES
        self.tabview = ctk.CTkTabview(self.left_frame)
        self.tabview.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.tab_maps = self.tabview.add("Яндекс.Карты")
        self.tab_freelance = self.tabview.add("Биржи фриланса")
        
        # --- TAB: YANDEX MAPS ---
        self.tab_maps.grid_columnconfigure(0, weight=1)
        self.tab_maps.grid_rowconfigure(7, weight=1)
        self.tab_maps.grid_rowconfigure(10, weight=1)

        self.var_maps = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(self.tab_maps, text="Включить парсинг Карт", variable=self.var_maps, font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(5, 5))
        
        self.var_headless = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.tab_maps, text="Скрытый браузер", variable=self.var_headless).grid(row=1, column=0, sticky="w", padx=10, pady=2)
        
        self.var_no_website = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.tab_maps, text="Только без сайта", variable=self.var_no_website).grid(row=2, column=0, sticky="w", padx=10, pady=2)
        
        self.var_has_phone = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.tab_maps, text="Только с телефоном", variable=self.var_has_phone).grid(row=3, column=0, sticky="w", padx=10, pady=(2, 10))
        
        self.lbl_limit = ctk.CTkLabel(self.tab_maps, text="Лимит парсинга (на город/нишу): 20")
        self.lbl_limit.grid(row=4, column=0, sticky="w", padx=10)
        self.limit_slider = ctk.CTkSlider(self.tab_maps, from_=10, to=100, number_of_steps=9, command=self.update_limit_lbl)
        self.limit_slider.set(20)
        self.limit_slider.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(self.tab_maps, text="Выберите города:").grid(row=6, column=0, sticky="w", padx=10)
        city_frame = ctk.CTkScrollableFrame(self.tab_maps, height=250)
        city_frame.grid(row=7, column=0, sticky="nsew", padx=10, pady=5)
        for i, city in enumerate(CITIES):
            var = ctk.BooleanVar(value=(i==0))
            chk = ctk.CTkCheckBox(city_frame, text=city, variable=var)
            chk.pack(anchor="w", pady=2)
            self.city_vars[city] = var
            
        self.custom_cities_entry = ctk.CTkEntry(self.tab_maps, placeholder_text="Свои города (через запятую)")
        self.custom_cities_entry.grid(row=8, column=0, sticky="ew", padx=10, pady=5)
            
        ctk.CTkLabel(self.tab_maps, text="Выберите ниши:").grid(row=9, column=0, sticky="w", padx=10, pady=(5,0))
        niche_frame = ctk.CTkScrollableFrame(self.tab_maps, height=250)
        niche_frame.grid(row=10, column=0, sticky="nsew", padx=10, pady=5)
        for i, niche in enumerate(NICHES):
            var = ctk.BooleanVar(value=(i==0))
            chk = ctk.CTkCheckBox(niche_frame, text=niche, variable=var)
            chk.pack(anchor="w", pady=2)
            self.niche_vars[niche] = var
            
        self.custom_niches_entry = ctk.CTkEntry(self.tab_maps, placeholder_text="Свои ниши (через запятую)")
        self.custom_niches_entry.grid(row=11, column=0, sticky="ew", padx=10, pady=5)
        
        # --- TAB: FREELANCE ---
        self.var_freelance = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(self.tab_freelance, text="Включить парсинг бирж", variable=self.var_freelance, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 10))
        
        self.var_fl = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.tab_freelance, text="FL.ru", variable=self.var_fl).pack(anchor="w", padx=10, pady=5)
        
        self.var_kwork = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.tab_freelance, text="Kwork", variable=self.var_kwork).pack(anchor="w", padx=10, pady=5)
        
        self.lbl_pages = ctk.CTkLabel(self.tab_freelance, text="Кол-во страниц (глубина): 2")
        self.lbl_pages.pack(anchor="w", padx=10, pady=(15, 0))
        
        self.pages_slider = ctk.CTkSlider(self.tab_freelance, from_=1, to=10, number_of_steps=9, command=self.update_pages_lbl)
        self.pages_slider.set(2)
        self.pages_slider.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.tab_freelance, text="Ключевые слова (через запятую):").pack(anchor="w", padx=10, pady=(10, 0))
        self.custom_keywords_entry = ctk.CTkEntry(self.tab_freelance, placeholder_text=", ".join(FREELANCE_KEYWORDS[:3]) + "...")
        self.custom_keywords_entry.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(self.tab_freelance, text="Мин. бюджет (число, 0 = любой):").pack(anchor="w", padx=10, pady=(10, 0))
        self.min_budget_entry = ctk.CTkEntry(self.tab_freelance, placeholder_text="Например: 5000")
        self.min_budget_entry.pack(fill="x", padx=10, pady=5)
        
        # BOTTOM CONTROLS (Always visible)
        self.controls_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.controls_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.run_btn = ctk.CTkButton(self.controls_frame, text="▶ Запустить парсинг", height=40, fg_color="green", hover_color="darkgreen", command=self.start_parsing)
        self.run_btn.pack(fill="x", pady=5)
        
        self.stop_btn = ctk.CTkButton(self.controls_frame, text="🛑 Остановить парсинг", height=40, fg_color="red", hover_color="darkred", state="disabled", command=self.stop_parsing)
        self.stop_btn.pack(fill="x", pady=5)
        
        self.folder_btn = ctk.CTkButton(self.controls_frame, text="📁 Открыть папку с базами", height=40, command=self.open_output_folder)
        self.folder_btn.pack(fill="x", pady=5)
        
        # RIGHT PANEL (Logs)
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(self.right_frame, text="Журнал работы", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=(10, 5))
        
        self.log_box = ctk.CTkTextbox(self.right_frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.log_box.insert("0.0", "Интерфейс готов к работе.\nВыберите нужный режим во вкладках слева и нажмите Запустить.\n")
        
        self.progress = ctk.CTkProgressBar(self.right_frame)
        self.progress.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.progress.set(0.0)
        
        # Bind close event to save settings
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.save_settings()
        self.destroy()

    def update_pages_lbl(self, val):
        self.lbl_pages.configure(text=f"Кол-во страниц (глубина): {int(val)}")

    def update_limit_lbl(self, val):
        self.lbl_limit.configure(text=f"Лимит парсинга (на город/нишу): {int(val)}")

    def save_settings(self):
        settings = {
            "var_maps": self.var_maps.get(),
            "var_headless": self.var_headless.get(),
            "var_no_website": self.var_no_website.get(),
            "var_has_phone": self.var_has_phone.get(),
            "limit_slider": self.limit_slider.get(),
            "custom_cities": self.custom_cities_entry.get(),
            "custom_niches": self.custom_niches_entry.get(),
            "city_vars": {city: var.get() for city, var in self.city_vars.items()},
            "niche_vars": {niche: var.get() for niche, var in self.niche_vars.items()},
            
            "var_freelance": self.var_freelance.get(),
            "var_fl": self.var_fl.get(),
            "var_kwork": self.var_kwork.get(),
            "pages_slider": self.pages_slider.get(),
            "custom_keywords": self.custom_keywords_entry.get(),
            "min_budget": self.min_budget_entry.get(),
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        if not self.settings_file.exists():
            return
            
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
                
            self.var_maps.set(settings.get("var_maps", True))
            self.var_headless.set(settings.get("var_headless", True))
            self.var_no_website.set(settings.get("var_no_website", True))
            self.var_has_phone.set(settings.get("var_has_phone", True))
            
            if "limit_slider" in settings:
                self.limit_slider.set(settings["limit_slider"])
                self.update_limit_lbl(settings["limit_slider"])
                
            self.custom_cities_entry.insert(0, settings.get("custom_cities", ""))
            self.custom_niches_entry.insert(0, settings.get("custom_niches", ""))
            
            for city, val in settings.get("city_vars", {}).items():
                if city in self.city_vars:
                    self.city_vars[city].set(val)
                    
            for niche, val in settings.get("niche_vars", {}).items():
                if niche in self.niche_vars:
                    self.niche_vars[niche].set(val)
                    
            self.var_freelance.set(settings.get("var_freelance", False))
            self.var_fl.set(settings.get("var_fl", True))
            self.var_kwork.set(settings.get("var_kwork", True))
            
            if "pages_slider" in settings:
                self.pages_slider.set(settings["pages_slider"])
                self.update_pages_lbl(settings["pages_slider"])
                
            self.custom_keywords_entry.insert(0, settings.get("custom_keywords", ""))
            self.min_budget_entry.insert(0, settings.get("min_budget", ""))
            
        except Exception as e:
            print(f"Error loading settings: {e}")

    def log(self, msg: str):
        def append():
            self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            self.log_box.see("end")
        self.after(0, append)

    def start_parsing(self):
        self.save_settings()
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log("▶ Начало работы. Сборка потоков...")
        self.progress.set(0.0)
        self.maps_leads = []
        self.fl_leads = []
        self.thread = threading.Thread(target=self._parsing_thread, daemon=True)
        self.thread.start()

    def stop_parsing(self):
        self.log("🛑 Прерывание парсинга...")
        self.stop_btn.configure(state="disabled")
        if hasattr(self, '_main_task') and self._main_task:
            if hasattr(self, '_asyncio_loop') and self._asyncio_loop.is_running():
                self._asyncio_loop.call_soon_threadsafe(self._main_task.cancel)

    def open_output_folder(self):
        out_dir = Path("Базы_клиентов_Excel").absolute()
        out_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            import os
            os.startfile(out_dir)

    def _play_success_sound(self):
        if winsound:
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except:
                pass

    def _export_results(self):
        if self.maps_leads or self.fl_leads:
            self.log(f"💾 Сохраняем в Excel (Карты: {len(self.maps_leads)}, Биржи: {len(self.fl_leads)})...")
            out_path = Path("Базы_клиентов_Excel") / f"Лиды_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            export_to_excel(self.maps_leads, self.fl_leads, output_path=out_path)
            self.log(f"✅ Готово! Сохранено в файл:\n{out_path.parent.absolute()}")
            self._play_success_sound()
            if sys.platform == "win32":
                import os
                os.startfile(out_path.parent.absolute())
        else:
            self.log("⚠️ Нет данных для сохранения.")
            
        self.after(0, lambda: self.progress.set(1.0))
        self.after(0, lambda: self.run_btn.configure(state="normal"))
        self.after(0, lambda: self.stop_btn.configure(state="disabled"))

    def _parsing_thread(self):
        import asyncio
        try:
            self._asyncio_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._asyncio_loop)
            self._main_task = self._asyncio_loop.create_task(self._async_parsing())
            self._asyncio_loop.run_until_complete(self._main_task)
        except asyncio.CancelledError:
            self.log("🛑 Парсинг прерван пользователем. Идет сохранение...")
        except Exception as e:
            self.log(f"Критическая ошибка: {e}")
        finally:
            self._export_results()
            try:
                self._asyncio_loop.close()
            except:
                pass

    async def _async_parsing(self):
        use_maps = self.var_maps.get()
        use_freelance = self.var_freelance.get()
        
        if not use_maps and not use_freelance:
            self.log("⚠️ Не включен ни один из режимов парсинга!")
            return
            
        use_fl = self.var_fl.get() if use_freelance else False
        use_kwork = self.var_kwork.get() if use_freelance else False
        
        sources_cnt = 0
        if use_maps: sources_cnt += 1
        if use_fl: sources_cnt += 1
        if use_kwork: sources_cnt += 1
        
        if sources_cnt == 0:
            self.log("⚠️ Не выбран ни один источник!")
            return
            
        # Parse custom cities and niches
        custom_c_text = self.custom_cities_entry.get().strip()
        custom_n_text = self.custom_niches_entry.get().strip()
        
        selected_cities = [city for city, var in self.city_vars.items() if var.get()]
        if custom_c_text:
            selected_cities.extend([c.strip() for c in custom_c_text.split(",") if c.strip()])
            
        selected_niches = [niche for niche, var in self.niche_vars.items() if var.get()]
        if custom_n_text:
            selected_niches.extend([n.strip() for n in custom_n_text.split(",") if n.strip()])
        
        if use_maps and (not selected_cities or not selected_niches):
            self.log("⚠️ Для Яндекс.Карт нужно выбрать/ввести хотя бы 1 город и 1 нишу!")
            return

        # Parse freelance filters
        custom_kw_text = self.custom_keywords_entry.get().strip()
        keywords = []
        if custom_kw_text:
            keywords = [k.strip() for k in custom_kw_text.split(",") if k.strip()]
            
        min_budget_text = self.min_budget_entry.get().strip().replace(" ", "")
        min_budget = 0
        if min_budget_text.isdigit():
            min_budget = int(min_budget_text)

        step = [0]
        def update_progress(msg):
            step[0] += 1
            self.log(msg)
            self.after(0, lambda: self.progress.set(step[0] / sources_cnt))

        if use_maps:
            self.log(f"▶ Парсинг Яндекс.Карт ({len(selected_cities)} городов, {len(selected_niches)} ниш)...")
            limit = int(self.limit_slider.get())
            await scrape_yandex_maps(
                cities=selected_cities,
                niches=selected_niches,
                max_per_query=limit,
                headless=self.var_headless.get(),
                no_website=self.var_no_website.get(),
                has_phone=self.var_has_phone.get(),
                on_lead=lambda lead: self.maps_leads.append(lead)
            )
            update_progress(f"✅ Яндекс.Карты завершены")
            
        pages = int(self.pages_slider.get())
        if use_fl:
            self.log(f"▶ Парсинг FL.ru ({pages} стр)...")
            await scrape_fl_ru(
                pages=pages,
                custom_keywords=keywords if keywords else None,
                min_budget=min_budget,
                on_lead=lambda lead: self.fl_leads.append(lead)
            )
            update_progress(f"✅ FL.ru завершен")
            
        if use_kwork:
            self.log(f"▶ Парсинг Kwork ({pages} стр)...")
            await scrape_kwork(
                pages=pages,
                custom_keywords=keywords if keywords else None,
                min_budget=min_budget,
                on_lead=lambda lead: self.fl_leads.append(lead)
            )
            update_progress(f"✅ Kwork завершен")

if __name__ == "__main__":
    app = App()
    app.mainloop()
