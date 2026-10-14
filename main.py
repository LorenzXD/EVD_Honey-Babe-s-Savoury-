from pyscript import document
from pyodide.ffi import create_proxy
import js
import random
import re

PRODUCTS = [
  {"id":1, "name":"Puto Cheese", "cat":"Kakanin", "price":2.50, "rating":4.9, "desc":"Soft steamed rice cakes crowned with melty cheese. To taste is to believe!", "img":"https://images.unsplash.com/photo-1486427944299-d1955d23e34d?auto=format&fit=crop&w=600&q=80"},
  {"id":2, "name":"Macaroons", "cat":"Cookies", "price":3.20, "rating":4.8, "desc":"Golden Filipino coconut macaroons — crisp outside, chewy inside.", "img":"https://images.unsplash.com/photo-1569864358642-9d1684040f43?auto=format&fit=crop&w=600&q=80"},
  {"id":3, "name":"Leche Flan", "cat":"Chilled", "price":4.50, "rating":4.9, "desc":"Silky caramel custard, slow-steamed the traditional way.", "img":"https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=600&q=80"},
  {"id":4, "name":"Maja Blanca", "cat":"Kakanin", "price":3.80, "rating":4.8, "desc":"Creamy coconut pudding crowned with toasted latik crunch.", "img":"https://images.unsplash.com/photo-1621303837174-89787a7d4729?auto=format&fit=crop&w=600&q=80"},
  {"id":5, "name":"Mango Float", "cat":"Chilled", "price":5.20, "rating":4.9, "desc":"Layers of ripe mango, sweet cream & graham. Chill, slice, smile.", "img":"https://images.unsplash.com/photo-1553279768-865429fa0078?auto=format&fit=crop&w=600&q=80"},
  {"id":6, "name":"Banana Cake", "cat":"Cakes", "price":4.00, "rating":4.7, "desc":"Moist banana cake with a caramelized golden top.", "img":"https://images.unsplash.com/photo-1586444248902-2f64eddc13df?auto=format&fit=crop&w=600&q=80"},
  {"id":7, "name":"Chicken Cordon Bleu", "cat":"Savory", "price":6.80, "rating":4.8, "desc":"Crispy chicken rolled with ham & cheese, served with creamy dip.", "img":"https://images.unsplash.com/photo-1598103442097-8b74394b95c6?auto=format&fit=crop&w=600&q=80"},
  {"id":8, "name":"Polvoron", "cat":"Cookies", "price":2.00, "rating":4.7, "desc":"Buttery toasted-flour shortbread that melts in your mouth.", "img":"https://images.unsplash.com/photo-1499636136210-6f4ee915583e?auto=format&fit=crop&w=600&q=80"},
]

cart = {}  # id -> qty
active_cat = "All"
search_q = ""

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
    return f"${n:.2f}"

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
        if q and q not in p["name"].lower() and q not in p["desc"].lower():
            continue
        out.append(p)
    return out

def render_menu():
    grid = _el("#menu-grid")
    if grid is None:
        return
    items = filtered_products()
    _set_text("#menu-count", f"{len(items)} treat{'s' if len(items)!=1 else ''}")
    if not items:
        try:
            grid.innerHTML = "<div style='grid-column:1/-1;background:var(--cream);border:1px dashed var(--maroon-light);padding:28px;border-radius:16px;text-align:center'>😢 No pastries match — try clearing search in Python!</div>"
        except Exception as err:
            js.console.warn(f"[HoneyBabe] render_menu failed: {err}")
        return
    html = ""
    for p in items:
        html += f"""
        <div class="card">
          <div class="card-img">
            <img src="{p['img']}" alt="{p['name']}" loading="lazy" onerror="this.src='https://placehold.co/600x400/f6eee1/7d4444?text=Pastry'" />
            <span class="cat-badge">{p['cat']}</span>
            <span class="price-badge">{money(p['price'])}</span>
          </div>
          <div class="card-body">
            <h3>{p['name']}</h3>
            <p>{p['desc']}</p>
            <div class="card-foot">
              <span class="rating">★ {p['rating']}</span>
              <button class="add-btn" data-id="{p['id']}" py-click="add_to_cart">Add +</button>
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
    disc = round(sub*0.10,2) if sub >= 20 else 0.0
    return sub, disc, sub-disc

def update_cart_ui():
    count = sum(cart.values())
    _set_text("#cart-count", str(count))
    sub, disc, total = cart_totals()
    _set_text("#cart-subtotal", money(sub))
    _set_text("#cart-discount", f"-{money(disc)}")
    _set_text("#cart-total", money(total))
    _set_text("#mini-total", money(total))
    box = _el("#cart-items")
    if box is None:
        return
    if not cart:
        _set_text("#mini-detail", "Cart is empty — add something flaky!")
        try:
            box.innerHTML = "<div style='text-align:center;color:var(--muted);padding:30px'>🧺 Your basket is empty.<br>Add a croissant, you deserve it.</div>"
        except Exception as err:
            js.console.warn(f"[HoneyBabe] update_cart_ui failed: {err}")
        return
    _set_text("#mini-detail", f"{count} item(s) · discount {money(disc)} applied by Python" if disc else f"{count} item(s) · add {money(20-sub)} more for 10% off")
    html = ""
    for pid, qty in cart.items():
        p = next(x for x in PRODUCTS if x["id"]==pid)
        html += f"""
        <div class="cart-item">
          <img src="{p['img']}" onerror="this.src='https://placehold.co/100x100/f6eee1/7d4444?text=Yum'" />
          <div><b style="font-size:.9rem">{p['name']}</b><br><small style="color:var(--muted)">{money(p['price'])} each</small><br><b>{money(p['price']*qty)}</b></div>
          <div class="qty">
            <button data-id="{pid}" data-act="dec" py-click="change_qty">−</button>
            <b>{qty}</b>
            <button data-id="{pid}" data-act="inc" py-click="change_qty">+</button>
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
    show_toast(f"Added {name['name']} 🥐 (Python cart: {sum(cart.values())})")

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
        show_toast("Basket is empty — add a pastry first 🍩")
        return
    close_all()
    sub, disc, total = cart_totals()
    _set_text("#checkout-summary", f"{sum(cart.values())} items · Total {money(total)} (saved {money(disc)})")
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
    time = _get_value("#f-time") or "ASAP (~15 min)"
    notes = _get_value("#f-notes").strip()
    if len(name) < 2:
        show_toast("Please tell Python your name 🙏")
        return
    if len(re.sub(r"\D","",phone)) < 7:
        show_toast("Hmm, that phone looks short 📞")
        return
    sub, disc, total = cart_totals()
    order_no = random.randint(1000,9999)
    _set_display("#order-form", "none")
    _set_display("#order-success", "block")
    _set_html("#order-success-text", f"Thanks <b>{name}</b>! Order <b>#HB-{order_no}</b> · {sum(cart.values())} items · <b>{money(total)}</b><br>Pickup: {time}<br>We'll text {phone}. {('Note saved: '+notes) if notes else ''}")
    cart.clear()
    update_cart_ui()
    show_toast(f"Order #HB-{order_no} placed! 🎉")

def clear_cart(event=None):
    cart.clear()
    update_cart_ui()
    show_toast("Basket cleared 🧹")

def say_hello(event=None):
    show_toast(f"Hello sweet tooth! 🍯 We have {len(PRODUCTS)} fresh treats today.")

def chef_surprise(event=None):
    p = random.choice(PRODUCTS)
    _set_html("#chef-output", f"👨‍🍳 Python chef suggests: <b>{p['name']}</b> — {p['desc']} <b>{money(p['price'])}</b>")
    show_toast(f"Chef's pick: {p['name']} ✨")

def subscribe_newsletter(event=None):
    email = _get_value("#newsletter-email").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        _set_text("#newsletter-msg", "⚠️ That email looks off — Python says try again.")
        node = _el("#newsletter-msg")
        if node is not None:
            try:
                node.style.color = "#b3261e"
            except Exception:
                pass
        return
    _set_text("#newsletter-msg", f"🎉 Welcome {email}! Fresh-bake alerts ON.")
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
    show_toast("Subscribed! 🥐")

# ---------- init: only after the DOM is ready, never crash ----------

def _init(*_args):
    try:
        render_menu()
        update_cart_ui()
        _set_html("#py-status", "✅ <b>PyScript kitchen is live!</b> Menu, cart & checkout are running in Python 🐍 (main.py)")
        _set_text("#float-special", random.choice(PRODUCTS)["name"])
    except Exception as err:
        try:
            js.console.error(f"[HoneyBabe] init failed: {err}")
        except Exception:
            pass
        _set_html("#py-status", "⚠️ Python had trouble starting — please refresh the page.")

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
