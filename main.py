from pyscript import document
from pyodide.ffi import create_proxy
import js
import html
import random
import re

# 12 house signatures — categories match the filter chips in index.html:
# All / Kakanin / Cakes / Cookies / Chilled / Savory
PRODUCTS = [
  {"id":1, "name":"Puto Cheese (4 pcs)", "cat":"Kakanin", "price":2.50, "rating":4.9, "desc":"Cloud-soft steamed rice cakes crowned with melty cheese. Our #1 merienda box.", "img":"https://images.unsplash.com/photo-1486427944299-d1955d23e34d?auto=format&fit=crop&w=600&q=80"},
  {"id":2, "name":"Coconut Macaroons (6 pcs)", "cat":"Cookies", "price":3.20, "rating":4.8, "desc":"Golden Filipino coconut macaroons — crisp edges, chewy centers, baked hourly.", "img":"https://images.unsplash.com/photo-1569864358642-9d1684040f43?auto=format&fit=crop&w=600&q=80"},
  {"id":3, "name":"Classic Leche Flan", "cat":"Chilled", "price":4.50, "rating":4.9, "desc":"Silky caramel custard, slow-steamed the traditional way. Jiggly & rich.", "img":"https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=600&q=80"},
  {"id":4, "name":"Maja Blanca Cup", "cat":"Kakanin", "price":3.80, "rating":4.8, "desc":"Creamy coconut pudding with sweet corn, crowned with toasted latik crunch.", "img":"https://images.unsplash.com/photo-1621303837174-89787a7d4729?auto=format&fit=crop&w=600&q=80"},
  {"id":5, "name":"Mango Float Tub", "cat":"Chilled", "price":5.20, "rating":4.9, "desc":"Layers of ripe mango, sweet cream & graham. Chilled overnight, sliced to order.", "img":"https://images.unsplash.com/photo-1553279768-865429fa0078?auto=format&fit=crop&w=600&q=80"},
  {"id":6, "name":"Classic Banana Cake", "cat":"Cakes", "price":4.00, "rating":4.7, "desc":"Extra-moist banana cake with a caramelized golden top. Coffee's best friend.", "img":"https://images.unsplash.com/photo-1606101273945-e9eba91c0dc4?auto=format&fit=crop&w=600&q=80"},
  {"id":7, "name":"Chicken Cordon Bleu Bites", "cat":"Savory", "price":6.80, "rating":4.8, "desc":"Crispy chicken rolled with ham & cheese, served with our signature creamy dip.", "img":"https://images.unsplash.com/photo-1598103442097-8b74394b95c6?auto=format&fit=crop&w=600&q=80"},
  {"id":8, "name":"Polvoron Assorted (5 pcs)", "cat":"Cookies", "price":2.00, "rating":4.7, "desc":"Buttery toasted-flour shortbread that melts in your mouth. Best pasalubong box.", "img":"https://images.unsplash.com/photo-1499636136210-6f4ee915583e?auto=format&fit=crop&w=600&q=80"},
  {"id":9, "name":"Ube Cheese Ensaymada", "cat":"Kakanin", "price":3.60, "rating":4.9, "desc":"Pillowy brioche swirled with real ube halaya, buttercream & grated cheese.", "img":"https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=600&q=80"},
  {"id":10, "name":"Mocha Chiffon Cake", "cat":"Cakes", "price":4.80, "rating":4.8, "desc":"Feather-light mocha chiffon with silky buttercream. Custom dedications free.", "img":"https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=600&q=80"},
  {"id":11, "name":"Ham & Cheese Pandesal (3 pcs)", "cat":"Savory", "price":3.40, "rating":4.7, "desc":"Toasted pandesal stuffed with ham & melted cheese. Served warm in 15 min.", "img":"https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=600&q=80"},
  {"id":12, "name":"Ube Flan Cake Slice", "cat":"Chilled", "price":5.80, "rating":4.9, "desc":"Our showstopper: ube chiffon + leche flan + caramel. Wedding favorite.", "img":"https://images.unsplash.com/photo-1464349095431-e9a21285b5f3?auto=format&fit=crop&w=600&q=80"},
]

cart = {}  # id -> qty
active_cat = "All"
search_q = ""
_review_rating = 5

# Hold JS proxies so the garbage collector never frees callbacks early.
_held_proxies = []

# ---------- safe DOM helpers (never crash on a missing node) ----------

def _el(sel):
    try:
        node = document.querySelector(sel)
    except Exception:
        node = None
    if node is None:
        js.console.warn(f"[HoneyBabe] element not found: {sel}")
    return node

def _set_text(sel, text):
    node = _el(sel)
    if node is not None:
        try:
            node.textContent = text
        except Exception as err:
            js.console.warn(f"[HoneyBabe] set_text failed for {sel}: {err}")

def _set_html(sel, html):
    node = _el(sel)
    if node is not None:
        try:
            node.innerHTML = html
        except Exception as err:
            js.console.warn(f"[HoneyBabe] set_html failed for {sel}: {err}")

def _set_display(sel, value):
    node = _el(sel)
    if node is not None:
        try:
            node.style.display = value
        except Exception as err:
            js.console.warn(f"[HoneyBabe] set_display failed for {sel}: {err}")

def _get_value(sel):
    node = _el(sel)
    if node is None:
        return ""
    try:
        return node.value or ""
    except Exception:
        return ""

def _later(fn, ms):
    try:
        proxy = create_proxy(fn)
        _held_proxies.append(proxy)
        js.setTimeout(proxy, ms)
    except Exception as err:
        js.console.warn(f"[HoneyBabe] timer failed: {err}")

# ---------- shop logic ----------

def money(n):
    return f"₱{n:.2f}"

def show_toast(msg):
    t = _el("#toast")
    if t is None:
        try:
            js.console.log(f"[toast] {msg}")
        except Exception:
            pass
        return
    try:
        t.textContent = msg
        t.classList.add("show")
    except Exception as err:
        js.console.warn(f"[HoneyBabe] toast failed: {err}")
        return
    _later(lambda: t.classList.remove("show"), 2200)

def filtered_products():
    q = search_q.strip().lower()
    out = []
    for p in PRODUCTS:
        if active_cat != "All" and p["cat"] != active_cat:
            continue
        if q and q not in p["name"].lower() and q not in p["desc"].lower() and q not in p["cat"].lower():
            continue
        out.append(p)
    return out

def render_menu():
    grid = _el("#menu-grid")
    if grid is None:
        return
    items = filtered_products()
    _set_text("#menu-count", f"{len(items)} treat{'s' if len(items)!=1 else ''} · baked fresh today")
    if not items:
        try:
            grid.innerHTML = "<div style='grid-column:1/-1;background:#fff;border:1px dashed var(--maroon-light);padding:28px;border-radius:16px;text-align:center'><svg style='width:22px;height:22px;color:var(--maroon);vertical-align:-4px' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='11' cy='11' r='8'/><line x1='21' y1='21' x2='16.65' y2='16.65'/></svg> No pastries match — try clearing your search or tapping All.</div>"
        except Exception as err:
            js.console.warn(f"[HoneyBabe] render_menu failed: {err}")
        return
    html = ""
    for p in items:
        badge = "<span class='best-badge'><svg style='width:11px;height:11px;vertical-align:-1px' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor' stroke='currentColor' stroke-width='1'><polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/></svg> BESTSELLER</span>" if p["rating"] >= 4.9 else ""
        html += f"""
        <div class="card">
          <div class="card-img">
            <img src="{p['img']}" alt="{p['name']}" loading="lazy" onerror="this.src='https://placehold.co/600x400/f6eee1/7d4444?text=Pastry'" />
            {badge}
            <span class="cat-badge">{p['cat']}</span>
            <span class="price-badge">{money(p['price'])}</span>
          </div>
          <div class="card-body">
            <h3>{p['name']}</h3>
            <p>{p['desc']}</p>
            <div class="card-foot">
              <span class="rating"><svg style="width:13px;height:13px;vertical-align:-2px;fill:currentColor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg> {p['rating']}</span>
              <button class="add-btn" data-id="{p['id']}" py-click="add_to_cart" aria-label="Add {p['name']} to basket">Add <svg style="width:13px;height:13px;vertical-align:-2px" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
            </div>
          </div>
        </div>
        """
    try:
        grid.innerHTML = html
    except Exception as err:
        js.console.warn(f"[HoneyBabe] render_menu failed: {err}")

def cart_totals():
    sub = sum(next(p for p in PRODUCTS if p["id"]==pid)["price"]*qty for pid,qty in cart.items())
    return sub, 0.0, sub

def update_cart_ui():
    count = sum(cart.values())
    _set_text("#cart-count", str(count))
    sub, disc, total = cart_totals()
    _set_text("#cart-subtotal", money(sub))
    _set_text("#cart-total", money(total))
    _set_text("#mini-total", money(total))
    box = _el("#cart-items")
    if box is None:
        return
    if not cart:
        _set_text("#mini-detail", "Cart is empty — add something flaky!")
        try:
            box.innerHTML = "<div style='text-align:center;color:var(--muted);padding:30px'><svg style='width:30px;height:30px;color:var(--maroon-light)' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z'/><line x1='3' y1='6' x2='21' y2='6'/><path d='M16 10a4 4 0 0 1-8 0'/></svg><br>Your basket is empty.<br>Add an ensaymada — you deserve it.<br><br><a href='#menu' style='font-weight:800;color:var(--maroon)'>Browse the menu</a></div>"
        except Exception as err:
            js.console.warn(f"[HoneyBabe] update_cart_ui failed: {err}")
        return
    _set_text("#mini-detail", f"{count} item(s) · {money(total)} total")
    html = ""
    for pid, qty in cart.items():
        p = next(x for x in PRODUCTS if x["id"]==pid)
        html += f"""
        <div class="cart-item">
          <img src="{p['img']}" alt="{p['name']}" onerror="this.src='https://placehold.co/100x100/f6eee1/7d4444?text=Yum'" />
          <div><b style="font-size:.9rem">{p['name']}</b><br><small style="color:var(--muted)">{money(p['price'])} each</small><br><b>{money(p['price']*qty)}</b></div>
          <div class="qty">
            <button data-id="{pid}" data-act="dec" py-click="change_qty" aria-label="Decrease quantity">−</button>
            <b>{qty}</b>
            <button data-id="{pid}" data-act="inc" py-click="change_qty" aria-label="Increase quantity">+</button>
          </div>
        </div>
        """
    try:
        box.innerHTML = html
    except Exception as err:
        js.console.warn(f"[HoneyBabe] update_cart_ui failed: {err}")

def _clicked_card_id(event):
    target = getattr(event, "target", None)
    if target is None:
        return None
    try:
        el = target.closest("[data-id]")
    except Exception:
        return None
    if el is None:
        return None
    try:
        return int(el.getAttribute("data-id"))
    except Exception:
        return None

# ---- events exposed to py-click / py-input / py-submit ----

def add_to_cart(event):
    pid = _clicked_card_id(event)
    if pid is None:
        return
    cart[pid] = cart.get(pid, 0) + 1
    update_cart_ui()
    name = next((p for p in PRODUCTS if p["id"]==pid), {"name":"treat"})
    show_toast(f"Added {name['name']} · {sum(cart.values())} in basket")

def change_qty(event):
    target = getattr(event, "target", None)
    if target is None:
        return
    try:
        el = target.closest("[data-id]")
    except Exception:
        el = None
    if el is None:
        return
    try:
        pid = int(el.getAttribute("data-id"))
        act = el.getAttribute("data-act")
    except Exception:
        return
    if act == "inc":
        cart[pid] = cart.get(pid,0)+1
    else:
        cart[pid] = cart.get(pid,0)-1
        if cart[pid] <= 0:
            cart.pop(pid, None)
    update_cart_ui()

def set_filter(event):
    global active_cat
    target = getattr(event, "target", None)
    if target is None:
        return
    try:
        active_cat = target.getAttribute("data-cat") or "All"
    except Exception:
        active_cat = "All"
    try:
        for c in document.querySelectorAll(".chip"):
            c.classList.remove("active")
        target.classList.add("active")
    except Exception as err:
        js.console.warn(f"[HoneyBabe] set_filter failed: {err}")
    render_menu()

def search_menu(event):
    global search_q
    target = getattr(event, "target", None)
    if target is None:
        return
    try:
        search_q = target.value or ""
    except Exception:
        search_q = ""
    render_menu()

def _toggle_cart(open_it):
    for sel, cls, on in (("#cart-drawer", "open", open_it), ("#overlay", "show", open_it)):
        node = _el(sel)
        if node is None:
            continue
        try:
            if on:
                node.classList.add(cls)
            else:
                node.classList.remove(cls)
        except Exception as err:
            js.console.warn(f"[HoneyBabe] toggle {sel} failed: {err}")

def open_cart(event=None):
    _toggle_cart(True)

def close_all(event=None):
    _toggle_cart(False)
    node = _el("#order-modal")
    if node is not None:
        try:
            node.classList.remove("show")
        except Exception:
            pass

def open_checkout(event=None):
    if not cart:
        show_toast("Basket is empty — add a pastry first")
        return
    close_all()
    sub, disc, total = cart_totals()
    _set_text("#checkout-summary", f"{sum(cart.values())} items · Total {money(total)}")
    _set_display("#order-form", "block")
    _set_display("#order-success", "none")
    node = _el("#order-modal")
    if node is not None:
        try:
            node.classList.add("show")
        except Exception:
            pass
    _toggle_cart(True)
    # hide the cart drawer but keep the overlay for the modal
    drawer = _el("#cart-drawer")
    if drawer is not None:
        try:
            drawer.classList.remove("open")
        except Exception:
            pass

def place_order(event):
    try:
        event.preventDefault()
    except Exception:
        pass
    name = _get_value("#f-name").strip()
    phone = _get_value("#f-phone").strip()
    address = _get_value("#f-address").strip()
    time = _get_value("#f-time") or "ASAP (~15 min)"
    notes = _get_value("#f-notes").strip()
    try:
        _sel = document.querySelector('input[name="pay"]:checked')
        pay = (_sel.value if _sel is not None else "COD") or "COD"
    except Exception:
        pay = "COD"
    gcash_ref = _get_value("#f-gcash-ref").strip()
    if pay not in ("COD", "GCash"):
        pay = "COD"
    if len(name) < 2:
        show_toast("Please tell us your name so we can label your box")
        return
    if len(re.sub(r"\D","",phone)) < 7:
        show_toast("Hmm, that phone looks short — we'll need it for pickup")
        return
    if len(address) < 5:
        show_toast("Please add your delivery address so we know where to bring it")
        return
    if pay == "GCash" and len(re.sub(r"\D", "", gcash_ref)) < 4:
        show_toast("Please enter your GCash reference number")
        return
    sub, disc, total = cart_totals()
    order_no = random.randint(1000,9999)
    _set_display("#order-form", "none")
    _set_display("#order-success", "block")
    _set_html("#order-success-text", f"Thanks <b>{html.escape(name)}</b>! Order <b>#HB-{order_no}</b> · {sum(cart.values())} items · <b>{money(total)}</b><br>Pickup: {html.escape(time)}<br>Deliver to: {html.escape(address)}<br>Payment: <b>{pay}</b>{(' (Ref ' + html.escape(gcash_ref) + ')') if pay == 'GCash' else ''}<br>We'll text {html.escape(phone)}. {('Note saved: '+html.escape(notes)) if notes else ''}")
    cart.clear()
    update_cart_ui()
    show_toast(f"Order #HB-{order_no} placed! See you soon")

def clear_cart(event=None):
    cart.clear()
    update_cart_ui()
    show_toast("Basket cleared")

def say_hello(event=None):
    show_toast(f"Hello sweet tooth! {len(PRODUCTS)} fresh treats baked today.")

def chef_surprise(event=None):
    p = random.choice(PRODUCTS)
    _set_html("#chef-output", f"<svg style='width:16px;height:16px;vertical-align:-3px;color:var(--orange-deep)' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 21a1 1 0 0 0 1-1v-5.35c0-.457.316-.844.727-1.041a4 4 0 0 0-2.134-7.589 5 5 0 0 0-9.186 0 4 4 0 0 0-2.134 7.588c.411.198.727.585.727 1.041V20a1 1 0 0 0 1 1Z'/><path d='M6 17h12'/></svg> Chef's pick: <b>{p['name']}</b> — {p['desc']} <b>{money(p['price'])}</b> · <svg style='width:13px;height:13px;vertical-align:-2px;fill:var(--orange-deep);color:var(--orange-deep)' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/></svg> {p['rating']}")
    show_toast(f"Chef's pick: {p['name']}")

def subscribe_newsletter(event=None):
    email = _get_value("#newsletter-email").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        _set_text("#newsletter-msg", "That email looks off — try again?")
        node = _el("#newsletter-msg")
        if node is not None:
            try:
                node.style.color = "#b3261e"
            except Exception:
                pass
        return
    _set_text("#newsletter-msg", f"Welcome {email}! Fresh-bake alerts ON — see you Friday.")
    node = _el("#newsletter-msg")
    if node is not None:
        try:
            node.style.color = "var(--maroon)"
        except Exception:
            pass
    email_node = _el("#newsletter-email")
    if email_node is not None:
        try:
            email_node.value = ""
        except Exception:
            pass
    show_toast("Subscribed! First alert drops Friday")

def _paint_stars(n):
    try:
        btns = document.querySelectorAll(".star-input button")
        for b in btns:
            try:
                v = int(b.getAttribute("data-stars") or 0)
            except Exception:
                v = 0
            try:
                if v <= n:
                    b.classList.add("active")
                else:
                    b.classList.remove("active")
            except Exception:
                pass
    except Exception as err:
        js.console.warn(f"[HoneyBabe] paint stars failed: {err}")

def set_rating(event=None):
    global _review_rating
    target = getattr(event, "target", None) if event is not None else None
    try:
        el = target.closest("[data-stars]") if target is not None else None
    except Exception:
        el = None
    if el is None:
        return
    try:
        _review_rating = max(1, min(5, int(el.getAttribute("data-stars") or 5)))
    except Exception:
        _review_rating = 5
    node = _el("#fb-rating")
    if node is not None:
        try:
            node.value = str(_review_rating)
        except Exception:
            pass
    _set_text("#fb-rating-label", f"Your rating: {_review_rating} star{'s' if _review_rating != 1 else ''}")
    _paint_stars(_review_rating)

def _review_stars_html(n):
    filled = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/></svg>"
    empty = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='#c9a87a' stroke-width='1.8'><polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/></svg>"
    return "<span class='stars-ico'>" + filled * n + empty * (5 - n) + "</span>"

def submit_review(event=None):
    try:
        event.preventDefault()
    except Exception:
        pass
    name = _get_value("#fb-name").strip()
    msg = _get_value("#fb-msg").strip()
    try:
        n = max(1, min(5, int(_get_value("#fb-rating") or _review_rating or 5)))
    except Exception:
        n = _review_rating
    if len(name) < 2:
        show_toast("Please add your name so we can credit your review")
        return
    if len(msg) < 3:
        show_toast("Please write a few words about your treat")
        return
    safe_name = html.escape(name[:40])
    safe_msg = html.escape(msg[:400])
    card = (
        "<div class='testi'>" + _review_stars_html(n) +
        "<p>\u201c" + safe_msg + "\u201d</p>" +
        "<div class='who'><div><b>" + safe_name + "</b><br>" +
        "<span class='verified'><svg style='width:12px;height:12px;vertical-align:-1px' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'/></svg> " +
        str(n) + "-star review</span></div></div></div>"
    )
    grid = _el(".testi-grid")
    if grid is None:
        show_toast("Review wall not found — please refresh")
        return
    try:
        grid.innerHTML = card + grid.innerHTML
    except Exception as err:
        js.console.warn(f"[HoneyBabe] submit_review failed: {err}")
        return
    for sel in ("#fb-name", "#fb-msg"):
        node = _el(sel)
        if node is not None:
            try:
                node.value = ""
            except Exception:
                pass
    show_toast(f"Thanks {name}! Your {n}-star review is live")

# ---------- init: only after the DOM is ready, never crash ----------

def _init(*_args):
    try:
        render_menu()
        update_cart_ui()
        _set_html("#py-status", "<svg style='width:16px;height:16px;vertical-align:-3px;color:#2e9e5b' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/><polyline points='9 12 11 14 15 10'/></svg> <b>Fresh-bake system live!</b> Menu, basket & checkout are ready — 12 treats today.")
        _set_text("#float-special", random.choice(PRODUCTS)["name"])
    except Exception as err:
        try:
            js.console.error(f"[HoneyBabe] init failed: {err}")
        except Exception:
            pass
        _set_html("#py-status", "Something had trouble starting — please refresh the page.")

try:
    _ready = js.document.readyState
except Exception:
    _ready = "complete"
if _ready == "loading":
    _init_proxy = create_proxy(_init)
    _held_proxies.append(_init_proxy)
    js.document.addEventListener("DOMContentLoaded", _init_proxy)
else:
    _init()
