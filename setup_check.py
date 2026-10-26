"""Opt-in local setup check. No screenshots, network traffic, or player history."""
import json
from pathlib import Path
import socket
import time


def run(m):
    rows = []
    def check(name, fn):
        try:
            detail = fn()
            rows.append(dict(check=name, passed=True, detail=detail or "OK"))
        except Exception as exc:
            # Do not put local paths, screen contents, or arbitrary errors in the report.
            rows.append(dict(check=name, passed=False, detail=type(exc).__name__))

    def assets():
        assert m.DigitTemplates.load(), "Missing digit templates"
        assert m.ICON_PATH.is_file(), "Missing icon"
        assert all((m.ASSETS / "fonts" / n).is_file() for n in m.FONT_FILES)
        return "Digit templates, icon and fonts found"

    def ocr():
        cmd = m.find_tesseract()
        assert cmd, "Bundled Tesseract missing"
        tess = m.ocr.Tesseract(cmd, timeout=20)
        img = m.np.full((100, 600), 255, dtype=m.np.uint8)
        m.cv2.putText(img, "123456789", (15, 70), m.cv2.FONT_HERSHEY_SIMPLEX, 2, 0, 3, m.cv2.LINE_AA)
        value = tess.read_line(img, "0123456789").replace(" ", "")
        assert value == "123456789", "Generated OCR sample was not read correctly"
        m.TESS, m.tesseract_ok = tess, True
        return "Bundled engine read generated digits through stdin"

    def potions():
        from potion_tracking import read_count, Usage
        from potion_recognition import Detector, AutoSelection, CountFont, HotbarDetector
        detector=Detector(m.ASSETS / "consumables")
        assert len(detector.catalog)==21
        assert HotbarDetector(m.ASSETS / "consumables",detector).frame is not None
        font=CountFont(m.ASSETS / "consumables")
        sample=m.np.full((15,33,3),200,dtype=m.np.uint8)
        x=1
        for c in "200":
            glyph=font.glyphs[int(c)];h,w=glyph.shape[:2];a=glyph[:,:,3:4]/255
            sample[2:2+h,x:x+w]=(glyph[:,:,:3]*a+sample[2:2+h,x:x+w]*(1-a)).astype(m.np.uint8)
            x+=w
        assert font.read(sample,36)==200, "Bundled count-font matching failed"
        assert detector.samples(m.np.zeros((300,300,3),dtype=m.np.uint8),[AutoSelection("Red Potion",2000000)])[0][0]==[]
        # Reproduce the light Classic World slot background and mixed stacks.
        frame=m.np.full((230,220,3),245,m.np.uint8)
        def paste(image,x,y):
            h,w=image.shape[:2];alpha=image[:,:,3:4]/255
            frame[y:y+h,x:x+w]=(image[:,:,:3]*alpha+frame[y:y+h,x:x+w]*(1-alpha)).astype(m.np.uint8)
        items={(3,0):(2000001,2),(0,1):(2000001,100),(4,0):(2010004,90)}
        for row in range(6):
            for col in range(5):
                x,y=12+col*36,12+row*34
                frame[y:y+30,x:x+32]=(213,223,225)
                if (col,row) not in items:continue
                item,count=items[(col,row)];ox,oy=detector.catalog[item]['origin']
                paste(detector.icons[item],x-ox,y+32-oy);xx=x+1
                for c in str(count):
                    glyph=font.glyphs[int(c)];paste(glyph,xx,y+20);xx+=glyph.shape[1]
        for scale in [1.25,1.5]:
            scaled=m.cv2.resize(frame,None,fx=scale,fy=scale,interpolation=m.cv2.INTER_LINEAR)
            found=detector.samples(scaled,[AutoSelection('Orange Potion',2000001),AutoSelection('Lemon',2010004)])
            values=[[font.read(image,box[2]) for box,image in stacks] for stacks,_ in found]
            assert values==[[2,100],[90]], 'Light inventory grid / multi-stack counts failed'
            repeated=detector.samples(scaled.copy(),[AutoSelection('Orange Potion',2000001),AutoSelection('Lemon',2010004)])
            assert [[font.read(image,box[2]) for box,image in stacks] for stacks,_ in repeated]==values, 'Fresh identical-pixel reuse changed counts'
        img = m.np.full((90, 240, 3), 25, dtype=m.np.uint8)
        m.cv2.putText(img, "200", (15, 65), m.cv2.FONT_HERSHEY_SIMPLEX, 2, (255,255,255), 3, m.cv2.LINE_AA)
        assert read_count(img, m.TESS) == 200, "Potion count OCR failed"
        use = Usage()
        for i, value in enumerate([200,199,198,197,196,195,194]):
            use.observe(value, i*3)
        assert use.used == 5 and use.per_minute() == 20
        use.gap(); use.observe(100,100); use.observe(99,103)
        assert use.used == 5, "Hidden usage should not be invented"
        return "Bundled 21-item catalog, light grid and Orange/Lemon multi-stack counts passed; generated OCR, rate and hidden-gap checks passed"

    def estimates():
        from potion_tracking import Usage
        use = Usage()
        for i in range(22):
            use.observe(200 - i, i * 3)
        assert (use.value,use.used,use.seconds,use.per_minute()) == (180,20,60,20)
        use.observe(500, 66); use.observe(499, 69)
        assert (use.used,use.seconds,use.per_minute()) == (20,60,20)
        original = time.monotonic
        clock = [0.0]
        try:
            time.monotonic = lambda: clock[0]
            session = m.Session(15)
            session.start(clock[0])
            def read(e, req=95700):
                return session.observe([(e, int(e / req * 10000) / 100)], True, clock[0])
            read(10000); read(10000)
            for i in range(1, 21):
                clock[0] = i * 3
                read(10000 + i * 100)
            assert abs(session.exp.rate() - 120000) < 1e-6
            rate = session.exp.rolling_rate() or session.exp.rate()
            eta = (session.exp.req - session.exp.exp) / rate * 3600
            assert abs(eta - 2511) < 1e-6
            session.pause(); clock[0] += 600
            assert session.exp.gained == 2000 and session.exp.elapsed() == 60
            assert abs(session.exp.rate() - 120000) < 1e-6
        finally:
            time.monotonic = original
        return "Known stock/usage rate, refill and original EXP/hour/level ETA/pause arithmetic passed"

    def network():
        try:
            socket.getaddrinfo("localhost", 80)
        except PermissionError:
            return "Python network guard blocked the request before DNS"
        raise AssertionError("Network guard was not active")

    def gui():
        root, app = None, None
        errors = []
        try:
            root = m.tk.Tk()
            app = m.App(root, m.DigitTemplates.load())
            # The setup check must never enable screen capture.
            assert not app.capture_enabled.is_set()
            root.report_callback_exception = lambda *args: errors.append(args[0].__name__)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                root.update()
                time.sleep(0.025)
            assert root.winfo_viewable() and app._worker_alive()
            app.open_potions()
            root.update()
            assert app.potion_win.winfo_exists() and not app.capture_enabled.is_set()
            panel=app.potion_win
            panel.scroll.fit();root.update()
            assert panel.winfo_height()<=panel.scroll.screen_bounds()[3]-100
            assert all(m.tkfont.Font(root=root,font=row.cget("font")).actual("family")==app.theme.font("regular",11).actual("family") for row in panel.rows)
            assert all(isinstance(button,m.Button) for button in panel.price_buttons)
            app.potion_win.destroy()
            app.open_settings()
            root.update()
            assert app.settings_win.winfo_exists()
            app.settings_win.scroll.fit();root.update()
            assert app.settings_win.winfo_height()<=app.settings_win.scroll.screen_bounds()[3]-100
            # Exercise the actual main-screen selector without screen capture.
            assert app.view.potions_btn.winfo_viewable()
            app.select_potion(0, 2000003)
            root.update()
            assert app.potion_slots[0].name == "Blue Potion" and app.view.potions_label.winfo_viewable()
            assert not app.capture_enabled.is_set()
            assert app.potion_price(0)==220 and "Using NPC reference" in app.potion_price_source(0)
            app.set_potion_price(0,"")
            assert app.potion_price(0) is None
            app.use_potion_npc_price(0)
            assert app.potion_price(0)==220
            app.set_potion_price(0,"50")
            assert app.potion_price(0)==50 and "Est. cost: 0 mesos" in app.potion_text(0)
            assert m.load_config()["potion_prices"]["2000003"]==50
            session, reader, worker = app.session, app.reader, app._worker_thread
            original_theme = app.cfg["theme"]
            app.set_compact(True)
            for mode in ("light", "dark", original_theme):
                app.set_theme(mode)
                root.update()
                expected = "#f3f5f9" if mode == "light" else "#0b0c10"
                assert root.cget("bg") == app.view.cget("bg") == expected
                assert app.session is session and app.reader is reader and app._worker_thread is worker
                assert app.view.hero.compact and not app.capture_enabled.is_set()
                assert m.load_config()["theme"] == mode
            app.set_compact(False)
            app.toggle_log()
            root.update()
            assert app.log_panel.winfo_viewable()
            app.open_colors()
            root.update()
            editor = app.color_win
            assert editor.winfo_viewable() and root.tk.call("info", "commands", "tk_chooseColor")
            editor.variables["exp"].set("#66ccff")
            editor.variables["meso"].set("#77ddaa")
            editor.variables["eta"].set("#dd99ff")
            editor.variables["progress"].set("#55bbcc")
            root.update()
            assert editor.save_button._enabled
            editor.save()
            root.update()
            assert app.theme.colors["exp"] == "#66ccff"
            assert m.load_config()["colors"][app.cfg["theme"]]["meso"] == "#77ddaa"
            assert app.session is session and app.reader is reader and app._worker_thread is worker
            app.open_colors()
            app.color_win.use_preset(None)
            app.color_win.save()
            root.update()
            assert not app.theme.colors
            app.settings_win.destroy()
            app.settings_win = None
            assert not errors and not app.capture_enabled.is_set()
            return "UI, saved themes/colors, main-screen item selection/NPC prices, matched potion fonts/buttons, bounded scrollable dialogs, compact/log views; capture stayed paused"
        finally:
            if app:
                app.close()
                app._worker_thread.join(timeout=3)
            elif root:
                root.destroy()

    check("Bundled assets", assets)
    check("Real OCR subprocess", ocr)
    check("Potion OCR and usage", potions)
    check("Estimate accuracy", estimates)
    check("Offline guard", network)
    check("Application UI", gui)
    passed = all(row["passed"] for row in rows)
    result = {"version": m.VERSION, "passed": passed, "checks": rows,
              "scope": "Setup only. No real game, screen capture, antivirus or anti-cheat certification."}
    out = Path.cwd()
    (out / "setup-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["Maple Private Overlay setup check: " + ("PASS" if passed else "FAIL")]
    lines += [("PASS " if r["passed"] else "FAIL ") + r["check"] + ": " + r["detail"] for r in rows]
    lines += [result["scope"]]
    (out / "setup-check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if passed else 1
