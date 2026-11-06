// Budgetuppföljningen: dölj diagram, fäll ihop grupper, markera kolumner och klicka i/ur kategorier.
(() => {
  const lagra = (typ, nyckel, varde) => { try { return varde === undefined ? window[typ].getItem(nyckel) : window[typ].setItem(nyckel, varde); } catch (e) { return null; } };

  // Dölj/visa diagrammet – valet kommer ihåg till nästa gång
  const graf = document.getElementById("budgetgraf");
  if (graf) {
    if (lagra("localStorage", "budgetgraf") === "dold") graf.removeAttribute("open");
    graf.addEventListener("toggle", () => lagra("localStorage", "budgetgraf", graf.open ? "visad" : "dold"));
  }

  // Behåll scrollläget när sidan laddas om efter att en kategori klickats i/ur
  const tabell = document.querySelector(".fast-rubrik");
  const sparat = lagra("sessionStorage", "budgetscroll");
  if (sparat) {
    lagra("sessionStorage", "budgetscroll", "");
    const [x, y, tx, ty] = sparat.split(",").map(Number);
    if (tabell) { tabell.scrollLeft = tx; tabell.scrollTop = ty; }
    window.scrollTo(x, y);
  }

  // Fäll ihop/ut grupper (t.ex. Boende, Mat) så att bara gruppens summarad syns. Kommer ihåg valet.
  const grupprader = [...document.querySelectorAll("table.uppf tr.grupp")];
  if (grupprader.length) {
    const ihop = new Set(JSON.parse(lagra("localStorage", "budgetgrupper_ihop") || "[]"));
    const detaljer = rad => {  // kategoriraderna direkt under en grupprad
      const r = [];
      for (let n = rad.nextElementSibling; n && n.classList.contains("kat"); n = n.nextElementSibling) r.push(n);
      return r;
    };
    const namn = rad => rad.cells[0].textContent.trim();
    const visa = rad => {
      const stangd = ihop.has(namn(rad));
      rad.classList.toggle("ihopfalld", stangd);
      rad.querySelector(".fall").setAttribute("aria-expanded", String(!stangd));
      detaljer(rad).forEach(d => d.hidden = stangd);
    };
    const spara = () => lagra("localStorage", "budgetgrupper_ihop", JSON.stringify([...ihop]));
    grupprader.forEach(rad => {
      const knapp = document.createElement("button");
      knapp.type = "button"; knapp.className = "fall"; knapp.title = "Fäll ihop/ut";
      knapp.addEventListener("click", () => {
        ihop.has(namn(rad)) ? ihop.delete(namn(rad)) : ihop.add(namn(rad));
        spara(); visa(rad);
      });
      rad.cells[0].prepend(knapp);
      visa(rad);
    });
    const verktyg = document.createElement("div");
    verktyg.className = "grupp-verktyg";
    [["Fäll ihop alla", true], ["Fäll ut alla", false]].forEach(([text, stang]) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "outline liten"; b.textContent = text;
      b.addEventListener("click", () => {
        grupprader.forEach(r => stang ? ihop.add(namn(r)) : ihop.delete(namn(r)));
        spara(); grupprader.forEach(visa);
      });
      verktyg.append(b);
    });
    document.querySelector(".fast-rubrik").before(verktyg);
  }

  // Klicka på en kolumnrubrik för att markera hela kolumnen (klicka igen för att ta bort markeringen)
  const tab = document.querySelector("table.uppf");
  if (tab) {
    const vy = "budgetkolumner:" + (new URL(location.href).searchParams.get("visa") || "manader");
    const markerade = new Set((lagra("sessionStorage", vy) || "").split(",").filter(Boolean).map(Number));
    const kolumner = rad => {  // [cell, första kolumn, antal kolumner] med hänsyn till colspan
      let k = 0;
      return [...rad.cells].map(c => { const r = [c, k, c.colSpan]; k += c.colSpan; return r; });
    };
    const rita = () => {
      tab.querySelectorAll("tr").forEach(rad => kolumner(rad).forEach(([c, start, antal]) => {
        const i = antal === 1 ? markerade.has(start) : false;
        const huvud = c.closest("thead") && [...Array(antal).keys()].every(n => markerade.has(start + n));
        c.classList.toggle("kolmark", i || !!huvud);
      }));
      lagra("sessionStorage", vy, [...markerade].join(","));
    };
    tab.querySelectorAll("thead tr").forEach(rad => kolumner(rad).forEach(([c, start, antal]) => {
      if (start === 0) return;  // kategorikolumnen
      c.classList.add("valbar");
      c.title = "Klicka för att markera kolumnen";
      c.addEventListener("click", () => {
        const alla = [...Array(antal).keys()].map(n => start + n);
        const pa = !alla.every(k => markerade.has(k));
        alla.forEach(k => pa ? markerade.add(k) : markerade.delete(k));
        rita();
      });
    }));
    rita();
  }

  // Klicka i/ur kategorier: de urklickade räknas inte i summorna (sparas i sessionen)
  document.querySelectorAll("label.ta-med input[data-kat]").forEach(cb => cb.addEventListener("change", () => {
    const ur = [...document.querySelectorAll("label.ta-med input[data-kat]")].filter(c => !c.checked).map(c => c.dataset.kat);
    lagra("sessionStorage", "budgetscroll", [window.scrollX, window.scrollY, tabell ? tabell.scrollLeft : 0, tabell ? tabell.scrollTop : 0].join(","));
    const url = new URL(location.href);
    url.searchParams.set("exkl", ur.join(","));
    location.replace(url.toString());
  }));
})();
