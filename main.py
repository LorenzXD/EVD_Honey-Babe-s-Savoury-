from pyscript import document
from pyodide.ffi import create_proxy
import js
import html
import random
import re

# 8 house signatures — categories match the filter chips in index.html:
# All / Kakanin / Cakes / Cookies / Chilled / Savory
PRODUCTS = [
  {"id":1, "name":"Puto Cheese Bites (50 pcs)", "cat":"Kakanin", "price":200, "rating":4.9, "desc":"Bite-size steamed rice cakes crowned with melty cheese — 50 pieces per box. Made for sharing.", "img":"./assets/puto-cheese.jpg", "pairing": "a merienda favorite with barako coffee"},
  {"id":2, "name":"Coconut Macaroons (30 pcs)", "cat":"Cookies", "price":150, "rating":4.8, "desc":"Golden Filipino coconut macaroons — crisp edges, chewy centers, baked hourly. 30 pieces per box.", "img":"./assets/macaroons.jpg", "pairing": "crisp with afternoon tea"},
  {"id":3, "name":"Classic Leche Flan (Tub)", "cat":"Chilled", "price":100, "rating":4.9, "desc":"Silky caramel custard, slow-steamed the traditional way. Jiggly & rich. Sold per tub.", "img":"./assets/leche-flan.png", "pairing": "black coffee's best friend"},
  {"id":4, "name":"Maja Blanca Tub", "cat":"Kakanin", "price":100, "rating":4.8, "desc":"Creamy coconut pudding with sweet corn, crowned with toasted latik crunch. Sold per tub.", "img":"./assets/maja-blanca.jpg", "pairing": "love it with toasted latik on top"},
  {"id":5, "name":"Mango Float Tub", "cat":"Chilled", "price":100, "rating":4.9, "desc":"Layers of ripe mango, sweet cream & graham. Chilled overnight, sliced to order. Sold per tub.", "img":"./assets/mango-float.png", "pairing": "the cool-down after lunch"},
  {"id":6, "name":"Classic Banana Cake (Tub)", "cat":"Cakes", "price":100, "rating":4.7, "desc":"Extra-moist banana cake with a caramelized golden top. Coffee's best friend. Sold per tub.", "img":"./assets/banana-cake.png", "pairing": "best beside a morning barako"},
  {"id":7, "name":"Chicken Cordon Bleu", "cat":"Savory", "price":6.80, "rating":4.8, "desc":"Crispy chicken rolled with ham & cheese, served with our signature creamy dip. Temporarily unavailable.", "img":"./assets/chicken-cordon.jpg", "pairing": "built for the creamy dip", "available": False},
  {"id":8, "name":"Polvoron Assorted (20 pcs)", "cat":"Cookies", "price":100, "rating":4.7, "desc":"Buttery toasted-flour shortbread that melts in your mouth. 20 pieces per box — the best pasalubong.", "img":"./assets/polvoron.jpg", "pairing": "the pasalubong-box hero"},
]

cart = {}  # id -> qty
active_cat = "All"
search_q = ""
_review_rating = 5

# Entrance stagger for the menu grid (re-armed on filter change, muted while typing).
_animate_menu = True

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
    if abs(n - round(n)) < 0.005:
        return f"₱{int(round(n)):,}"
    return f"₱{n:,.2f}"

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

def _menu_kinds(n):
    # Editorial 12-col composition: one full-width banner opener, optional wide
    # feature cards, the rest compact. Wides are added only in counts that keep
    # the grid rows full (all spans are multiples of 4 on a 12-col grid).
    if n < 6:
        return ["card"] * n
    kinds = ["card"] * n
    kinds[0] = "banner"
    m = n - 1
    w = 0
    while (4 * n + 8 + 4 * w) % 12 != 0:
        w += 1
    if w <= m:
        for k in range(w):
            kinds[1 + int((k + 0.5) * m / w)] = "wide"
    return kinds

def render_menu():
    global _animate_menu
    grid = _el("#menu-grid")
    if grid is None:
        return
    animate = _animate_menu
    _animate_menu = False
    items = filtered_products()
    if items:
        _set_text("#menu-count", f"{len(items)} of {len(PRODUCTS)} treats · baked fresh hourly")
    else:
        _set_text("#menu-count", "Nothing matched on today's list")
    if not items:
        try:
            grid.innerHTML = (
                "<div class='menu-empty'>"
                "<svg class='empty-ico' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='11' cy='11' r='8'/><line x1='21' y1='21' x2='16.65' y2='16.65'/></svg>"
                "<b>No pastries match that craving</b>"
                "<p>Try a different word or category — the oven's still ticking.</p>"
                "<button class='btn btn-outline btn-sm' py-click='reset_filters'>Show the full menu</button>"
                "</div>"
            )
        except Exception as err:
            js.console.warn(f"[HoneyBabe] render_menu failed: {err}")
        return
    star = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/></svg>"
    arrow = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'/><path d='m12 5 7 7-7 7'/></svg>"
    plus = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.4' stroke-linecap='round'><line x1='12' y1='5' x2='12' y2='19'/><line x1='5' y1='12' x2='19' y2='12'/></svg>"
    kinds = _menu_kinds(len(items))
    html = ""
    for idx, p in enumerate(items):
        available = p.get("available", True)
        best = "<b class='card-best'> · Bestseller</b>" if p["rating"] >= 4.9 else ""
        kind = kinds[idx]
        open_cls = "card enter" if animate else "card"
        if kind != "card":
            open_cls += " card--" + kind
        if not available:
            open_cls += " card--unavailable"
        card_style = f' style="--i:{idx}"' if animate else ""
        extra = ""
        if kind == "banner" and p.get("pairing"):
            extra = "<p class='card-pairing'><b>Pair it with</b> — " + p["pairing"] + "</p>"
        badge = "<span class='card-unavail'>Temporarily Unavailable</span>" if not available else ""
        if available:
            price_cls = "card-price"
            price_html = money(p['price'])
            add_btn = f'<button class="add-btn" data-id="{p["id"]}" py-click="add_to_cart" aria-label="Add {p["name"]} to basket">Add{plus}</button>'
        else:
            price_cls = "card-price card-price--unavailable"
            price_html = "Temporarily Unavailable"
            add_btn = f'<button class="add-btn" disabled aria-label="{p["name"]} is temporarily unavailable">Unavailable</button>'
        html += f"""
        <article class="{open_cls}"{card_style}>
          <button class="card-open" data-id="{p['id']}" py-click="open_dish" aria-label="View details of {p['name']}"></button>
          <div class="card-media">
            <img src="{p['img']}" alt="{p['name']}" loading="lazy" onerror="this.src='https://placehold.co/600x400/f7f1e5/40251c?text=Pastry'" />
            {badge}
            <span class="card-view">View details{arrow}</span>
          </div>
          <div class="card-body">
            <div class="card-meta">
              <span class="card-cat">{p['cat']}{best}</span>
              <span class="card-rating">{star}{p['rating']}</span>
            </div>
            <h3>{p['name']}</h3>
            <p>{p['desc']}</p>
            {extra}
          </div>
          <div class="card-foot">
            <span class="{price_cls}">{price_html}</span>
            {add_btn}
          </div>
        </article>
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
          <img src="{p['img']}" alt="{p['name']}" onerror="this.src='https://placehold.co/100x100/f7f1e5/40251c?text=Yum'" />
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
    p = next((x for x in PRODUCTS if x["id"] == pid), None)
    if p is None:
        return
    if not p.get("available", True):
        show_toast(f"{p['name']} is temporarily unavailable")
        return
    cart[pid] = cart.get(pid, 0) + 1
    update_cart_ui()
    show_toast(f"Added {p['name']} · {sum(cart.values())} in basket")

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
    global active_cat, _animate_menu
    target = getattr(event, "target", None)
    if target is None:
        return
    try:
        active_cat = target.getAttribute("data-cat") or "All"
    except Exception:
        active_cat = "All"
    _animate_menu = True
    _sync_chips()
    render_menu()

def _sync_chips():
    try:
        for c in document.querySelectorAll(".chip[data-cat]"):
            try:
                on = (c.getAttribute("data-cat") or "All") == active_cat
                c.classList.toggle("active", on)
                c.setAttribute("aria-pressed", "true" if on else "false")
            except Exception:
                pass
    except Exception as err:
        js.console.warn(f"[HoneyBabe] sync chips failed: {err}")

def reset_filters(event=None):
    global active_cat, search_q, _animate_menu
    active_cat = "All"
    search_q = ""
    _animate_menu = True
    node = _el("#search")
    if node is not None:
        try:
            node.value = ""
        except Exception:
            pass
    _sync_chips()
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
    _animate_menu = False
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
    node = _el("#dish-modal")
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

# ---------- pastry detail view ----------

_dish_id = None
_dish_qty = 1

def _dish_by_id(pid):
    return next(p for p in PRODUCTS if p["id"] == pid)

def _dish_paint():
    p = _dish_by_id(_dish_id)
    _set_text("#dish-qty", str(_dish_qty))
    node = _el("#dish-add")
    if node is not None:
        try:
            if p.get("available", True):
                node.disabled = False
                node.innerHTML = "Add to basket · " + money(p["price"] * _dish_qty)
            else:
                node.disabled = True
                node.textContent = "Temporarily Unavailable"
        except Exception as err:
            js.console.warn(f"[HoneyBabe] dish label failed: {err}")

def open_dish(event=None):
    global _dish_id, _dish_qty
    pid = _clicked_card_id(event)
    if pid is None:
        return
    _dish_id = pid
    _dish_qty = 1
    p = _dish_by_id(pid)
    img = _el("#dish-img")
    if img is not None:
        try:
            img.setAttribute("src", p["img"])
            img.setAttribute("alt", p["name"])
        except Exception:
            pass
    try:
        cat = _el("#dish-cat")
        if cat is not None:
            if p["rating"] >= 4.9:
                cat.innerHTML = html.escape(p["cat"]) + " <b>· Bestseller</b>"
            else:
                cat.textContent = p["cat"]
    except Exception as err:
        js.console.warn(f"[HoneyBabe] dish cat failed: {err}")
    _set_text("#dish-name", p["name"])
    _set_html("#dish-rating", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/></svg>" + f" {p['rating']}")
    _set_text("#dish-desc", p["desc"])
    heart = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z'/></svg>"
    flame = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z'/></svg>"
    truck = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='1' y='3' width='15' height='13' rx='1'/><path d='M16 8h4l3 3v5h-7V8z'/><circle cx='5.5' cy='18.5' r='2.5'/><circle cx='18.5' cy='18.5' r='2.5'/></svg>"
    _set_html("#dish-facts",
        "<li>" + heart + html.escape(p.get("pairing", "a house signature")) + "</li>"
        + "<li>" + flame + "Baked fresh hourly</li>"
        + "<li>" + truck + "Free delivery over ₱35</li>")
    _dish_paint()
    node = _el("#dish-modal")
    if node is not None:
        try:
            node.classList.add("show")
        except Exception:
            pass
    ov = _el("#overlay")
    if ov is not None:
        try:
            ov.classList.add("show")
        except Exception:
            pass

def close_dish(event=None):
    node = _el("#dish-modal")
    if node is not None:
        try:
            node.classList.remove("show")
        except Exception:
            pass
    ov = _el("#overlay")
    if ov is not None:
        try:
            ov.classList.remove("show")
        except Exception:
            pass

def dish_step(event=None):
    global _dish_qty
    if _dish_id is None:
        return
    target = getattr(event, "target", None)
    act = None
    if target is not None:
        try:
            act = target.getAttribute("data-act")
        except Exception:
            act = None
    if act == "up":
        _dish_qty = min(12, _dish_qty + 1)
    elif act == "down":
        _dish_qty = max(1, _dish_qty - 1)
    _dish_paint()

def add_dish_to_cart(event=None):
    global _dish_qty
    if _dish_id is None:
        return
    p = _dish_by_id(_dish_id)
    if not p.get("available", True):
        show_toast(f"{p['name']} is temporarily unavailable")
        return
    qty = _dish_qty
    cart[_dish_id] = cart.get(_dish_id, 0) + qty
    update_cart_ui()
    show_toast(f"Added {p['name']} × {qty}")
    _dish_qty = 1
    close_dish()

def say_hello(event=None):
    show_toast(f"Hello sweet tooth! {len(PRODUCTS)} treats on the menu today.")

def chef_surprise(event=None):
    p = random.choice([x for x in PRODUCTS if x.get("available", True)])
    _set_html(
        "#chef-output",
        "<svg class='ico' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 21a1 1 0 0 0 1-1v-5.35c0-.457.316-.844.727-1.041a4 4 0 0 0-2.134-7.589 5 5 0 0 0-9.186 0 4 4 0 0 0-2.134 7.588c.411.198.727.585.727 1.041V20a1 1 0 0 0 1 1Z'/><path d='M6 17h12'/></svg>"
        + " Chef's pick — <b>" + p['name'] + "</b> " + p['desc']
        + " <span class='pick-price'>" + money(p['price']) + "</span>"
        + "<button class='mini-add' data-id='" + str(p['id']) + "' py-click='add_to_cart'>Add to basket</button>"
    )
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
        _set_html("#py-status", "<svg style='width:16px;height:16px;vertical-align:-3px;color:#1e7a44' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/><polyline points='9 12 11 14 15 10'/></svg> <b>Fresh-bake system live!</b> Menu, basket & checkout are ready — " + str(len(PRODUCTS)) + " treats on the menu.")
        pick = random.choice([x for x in PRODUCTS if x.get("available", True)])
        _set_text("#float-special", pick["name"])
        img = _el("#float-special-img")
        if img is not None:
            try:
                img.setAttribute("src", pick["img"])
                img.setAttribute("alt", pick["name"])
            except Exception:
                pass
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
