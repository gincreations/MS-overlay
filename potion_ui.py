"""Local potion setup UI. Frozen game image exists only for selection, in memory."""
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
from PIL import Image, ImageTk

from potion_tracking import PRESETS, Selection
from ui_main import Window, Button, DialogScroll
import ui_palette
from ui_kit import BG, FG, DIM, SURFACE, RAISED, LINE


class PotionPicker(Window):
    def __init__(self, parent, frame, name, on_save, on_close):
        super().__init__(parent)
        self.title("Select a potion stack")
        self.configure(bg=BG)
        self.transient(parent)
        self.attributes("-topmost", True)
        self.frame, self.on_save, self.on_close = frame, on_save, on_close
        self.box = self.digits = None
        self.drag = None
        self.rect_id = None
        self.name = tk.StringVar(value=name)
        self.hint = tk.StringVar()
        tk.Label(self, text="Potion name (choose or type your own)", bg=BG, fg=FG).pack(anchor="w", padx=12, pady=(10, 2))
        ttk.Combobox(self, textvariable=self.name, values=PRESETS, width=35).pack(anchor="w", padx=12)
        tk.Label(self, textvariable=self.hint, bg=BG, fg=FG, wraplength=750, justify="left").pack(padx=12, pady=8)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=BG, cursor="crosshair")
        self.canvas.pack(padx=12)
        self.preview = tk.Label(self, bg=BG, fg=DIM, text="")
        self.preview.pack(padx=12, pady=6)
        controls = tk.Frame(self, bg=BG); controls.pack(fill="x", padx=12, pady=10)
        ttk.Button(controls, text="Start selection over", command=self.restart).pack(side="left")
        ttk.Button(controls, text="Cancel", command=self.destroy).pack(side="right")
        self.save_button = ttk.Button(controls, text="Track this potion", command=self.save, state="disabled")
        self.save_button.pack(side="right", padx=8)
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.motion)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda e: self.destroy())
        self.restart()

    def show_image(self, bgr, zoom=False):
        h, w = bgr.shape[:2]
        self.scale = min(6 if zoom else 1, max(100, self.winfo_screenwidth()-100)/w,
                         max(100, self.winfo_screenheight()-280)/h, 1000/w, 620/h)
        image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        image = image.resize((max(1,round(w*self.scale)), max(1,round(h*self.scale))), Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(image, master=self)
        self.canvas.delete("all")
        self.canvas.configure(width=image.width, height=image.height)
        self.canvas.create_image(0,0,anchor="nw",image=self.photo)
        self.bounds = (w,h)
        self.rect_id = None

    def restart(self):
        self.box = self.digits = None
        self.preview.configure(image="", text="Keep the selected inventory slot visible during tracking.")
        self.count_photo = None
        self.save_button.configure(state="disabled")
        self.hint.set("1 / 2: Drag around ONE complete potion slot: icon plus its stack count. Avoid neighbouring slots.")
        self.show_image(self.frame)

    def point(self, event):
        return (max(0,min(self.bounds[0],round(event.x/self.scale))),
                max(0,min(self.bounds[1],round(event.y/self.scale))))

    def press(self, event):
        self.drag = self.point(event)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(event.x,event.y,event.x,event.y,outline="#ffcc44",width=2)

    def motion(self, event):
        if self.drag is not None:
            x,y = self.drag; xx,yy = self.point(event)
            self.canvas.coords(self.rect_id,x*self.scale,y*self.scale,xx*self.scale,yy*self.scale)

    def release(self, event):
        if self.drag is None:
            return
        x,y=self.drag; xx,yy=self.point(event);self.drag=None
        box=(min(x,xx),min(y,yy),abs(xx-x),abs(yy-y))
        if min(box[2:])<5:
            self.hint.set("Drag a rectangle at least 5 pixels wide and high.")
            return
        if self.box is None:
            if max(box[2:])>180:
                self.hint.set("Choose just one potion slot (up to 180 × 180 pixels).")
                return
            self.box=box;x,y,w,h=box
            self.show_image(self.frame[y:y+h,x:x+w],zoom=True)
            self.hint.set("2 / 2: On this enlarged slot, drag tightly around ONLY the count digits, with a little margin.")
        else:
            self.digits=box
            try:
                self.selection()
            except ValueError as exc:
                self.hint.set(str(exc));self.save_button.configure(state="disabled");return
            x,y,_,_=self.box;dx,dy,dw,dh=box
            count=self.frame[y+dy:y+dy+dh,x+dx:x+dx+dw]
            image=Image.fromarray(cv2.cvtColor(count,cv2.COLOR_BGR2RGB)).resize((dw*4,dh*4),Image.Resampling.NEAREST)
            self.count_photo=ImageTk.PhotoImage(image,master=self)
            self.preview.configure(image=self.count_photo,text="")
            self.hint.set("Count preview below. Save, then click back into the game. Potion identity is your label, not automatic recognition.")
            self.save_button.configure(state="normal")

    def selection(self):
        if self.box is None or self.digits is None:
            raise ValueError("Select the slot and its count first.")
        return Selection.make(self.name.get(),self.frame,self.box,self.digits)

    def save(self):
        try:
            selection=self.selection()
        except ValueError as exc:
            self.hint.set(str(exc));return
        self.on_save(selection)
        self.destroy()

    def destroy(self):
        if self.on_close is not None:
            fn,self.on_close=self.on_close,None
            fn()
        self.frame=self.photo=self.count_photo=None
        super().destroy()


class PotionPanel(Window):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app=app
        self.title("Potion usage")
        self.configure(bg=BG)
        self.transient(parent)
        self.attributes("-topmost",bool(app.cfg["topmost"]))
        self.resizable(False,False)
        self.bind("<Escape>",lambda e:self.destroy())
        th=app.theme;px=th.px
        self.theme=th
        self.scroll=DialogScroll(self,BG)
        body=tk.Frame(self.scroll.body,bg=BG);body.pack(padx=px(18),pady=px(16))
        wrap=px(420)
        tk.Label(body,text="Potions & costs",bg=BG,fg=FG,font=th.font("bold",18)).pack(anchor="w")
        tk.Label(body,text="Optional: leave both items Off to disable potion tracking. When enabled, keep the inventory Use tab visible.",
                 bg=BG,fg=DIM,font=th.font("regular",11),wraplength=wrap,justify="left").pack(anchor="w",pady=(px(4),px(10)))
        style=ttk.Style(self)
        style.configure("Potion.TCombobox",fieldbackground=RAISED,background=RAISED,foreground=FG,
                        arrowcolor=FG,bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,padding=px(6))
        style.map("Potion.TCombobox",fieldbackground=[("readonly",RAISED)],foreground=[("readonly",FG)],
                  selectbackground=[("readonly",RAISED)],selectforeground=[("readonly",FG)])
        self.choices={"Off":None, **{r["name"]:i for i,r in app.potion_catalog.items()}}
        self.selectors=[];self.price_vars=[];self.price_items=[];self.price_entries=[]
        self.price_buttons=[];self.npc_buttons=[];self.price_sources=[];self.rows=[]
        for index in range(2):
            card=tk.Frame(body,bg=SURFACE,highlightthickness=1,highlightbackground=LINE)
            card.pack(fill="x",pady=(0,px(10)))
            row=tk.Frame(card,bg=SURFACE);row.pack(padx=px(12),pady=px(12),fill="x")
            tk.Label(row,text=f"ITEM {index+1}",bg=SURFACE,fg=DIM,font=th.font("semibold",10)).pack(anchor="w")
            controls=tk.Frame(row,bg=SURFACE);controls.pack(anchor="w",pady=(px(5),px(6)))
            current=app.potion_slots[index]
            selector=ttk.Combobox(controls,values=list(self.choices),state="readonly",width=19,
                                  font=th.font("semibold",12),style="Potion.TCombobox",height=12)
            selector.set(current.name if current else "Off")
            selector.bind("<<ComboboxSelected>>",lambda event,i=index,box=selector:self.choose_item(i,self.choices[box.get()]))
            selector.pack(side="left")
            # Scope the dropdown palette/font to this widget, not global Tk options.
            pop=self.tk.call("ttk::combobox::PopdownWindow",str(selector))
            if self.tk.call("winfo","exists",str(pop)+".f.l"):
                self.tk.call(str(pop)+".f.l","configure","-font",th.font("regular",12),"-background",RAISED,
                             "-foreground",FG,"-selectbackground",LINE,"-selectforeground",FG)
            self.selectors.append(selector)
            Button(controls,th,text="Resync",width=68,height=32,size=11,bg=SURFACE,
                   command=lambda i=index:app.reset_potion(i)).pack(side="left",padx=px(5))
            Button(controls,th,text="Remove",width=70,height=32,size=11,kind="ghost",bg=SURFACE,
                   command=lambda i=index:app.remove_potion(i)).pack(side="left")
            label=tk.Label(row,bg=SURFACE,fg=FG,font=th.font("regular",11),justify="left",wraplength=wrap,anchor="w")
            label.pack(fill="x",pady=(0,px(8)))
            prices=tk.Frame(row,bg=SURFACE);prices.pack(anchor="w")
            tk.Label(prices,text="Mesos / item",bg=SURFACE,fg=DIM,font=th.font("semibold",11)).pack(side="left")
            price=app.potion_price(index);var=tk.StringVar(value="" if price is None else f"{price:,}")
            entry=tk.Entry(prices,textvariable=var,width=10,font=th.font("regular",12),bg=RAISED,fg=FG,
                           insertbackground=FG,disabledbackground=SURFACE,disabledforeground=DIM,
                           relief="flat",highlightthickness=1,highlightbackground=LINE,highlightcolor=FG)
            entry.pack(side="left",padx=px(6),ipady=px(5))
            entry.bind("<Return>",lambda event,i=index:self.save_price(i))
            button=Button(prices,th,text="Save price",width=84,height=32,size=11,bg=SURFACE,command=lambda i=index:self.save_price(i))
            button.pack(side="left")
            npc_button=Button(prices,th,text="Use NPC",width=76,height=32,size=11,kind="ghost",bg=SURFACE,command=lambda i=index:self.use_npc(i))
            npc_button.pack(side="left",padx=px(3));self.npc_buttons.append(npc_button)
            source=tk.Label(row,bg=SURFACE,fg=DIM,font=th.font("regular",10),justify="left",wraplength=wrap,anchor="w")
            source.pack(fill="x",pady=(px(7),0));self.price_sources.append(source)
            self.price_vars.append(var);self.price_entries.append(entry);self.price_buttons.append(button)
            self.price_items.append(getattr(current,"item_id",None));self.rows.append(label)
        tk.Label(body,text="Selling/dropping can look like use; hidden stock is not included. Usage rates exclude hidden and paused time.",
                 bg=BG,fg=DIM,font=th.font("regular",10),wraplength=wrap,justify="left").pack(anchor="w",pady=(0,px(6)))
        tk.Label(body,text="NPC references: MapleClassic Wiki · Oct 20, 2026. Mostly pre-launch data; shops/ranks/prices may differ.",
                 bg=BG,fg=DIM,font=th.font("regular",10),wraplength=wrap,justify="left").pack(anchor="w",pady=(0,px(6)))
        self.price_message=tk.StringVar(value="Use your paid/average unit price. Blank hides costs; 0 = free. Use NPC restores the reference.")
        tk.Label(body,textvariable=self.price_message,bg=BG,fg=FG,font=th.font("regular",11),justify="left",wraplength=wrap).pack(anchor="w",pady=px(4))
        self.close_button=Button(body,th,text="Close",kind="primary",width=96,height=34,size=12,command=self.destroy,bg=BG)
        self.close_button.pack(anchor="e",pady=(px(8),0))
        self.refresh()

    def choose_item(self, index, item):
        self.app.select_potion(index,item)
        current=self.app.potion_slots[index]
        self.selectors[index].set(current.name if current else "Off")
        price=self.app.potion_price(index)
        self.price_vars[index].set("" if price is None else f"{price:,}")
        self.price_items[index]=getattr(current,"item_id",None)
        self.refresh_prices()

    def save_price(self, index):
        try:
            price=self.app.set_potion_price(index,self.price_vars[index].get())
        except ValueError as exc:
            self.price_message.set(str(exc));return
        self.price_vars[index].set("" if price is None else f"{price:,}")
        self.price_message.set("Price saved. Session estimates use this price; hidden/paused time is excluded."
                               if price is not None else "Cost display hidden. The item is still tracked.")
        self.refresh_prices()

    def use_npc(self, index):
        try:
            price=self.app.use_potion_npc_price(index)
        except ValueError as exc:
            self.price_message.set(str(exc));return
        self.price_vars[index].set(f"{price:,}")
        self.price_message.set("NPC reference restored. Check the shop/rank note; you can override it anytime.")
        self.refresh_prices()

    def refresh_prices(self):
        for i in range(2):
            self.price_sources[i].configure(text=self.app.potion_price_source(i))
            self.npc_buttons[i].set(enabled=self.app.potion_npc_price(i) is not None)

    def refresh(self):
        self.refresh_prices()
        for i,label in enumerate(self.rows):
            current=self.app.potion_slots[i]
            self.selectors[i].set(current.name if current else "Off")
            item=getattr(current,"item_id",None)
            if item!=self.price_items[i]:
                price=self.app.potion_price(i)
                self.price_vars[i].set("" if price is None else f"{price:,}")
                self.price_items[i]=item
            state="normal" if item is not None else "disabled"
            self.price_entries[i].configure(state=state);self.price_buttons[i].set(enabled=item is not None)
            label.configure(text=self.app.potion_text(i,details=False))
        self.after(500,self.refresh)

    def destroy(self):
        self.app.cancel_potion_request()
        super().destroy()

ui_palette.register(globals())
