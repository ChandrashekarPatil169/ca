/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DealerTracking = publicWidget.Widget.extend({
    selector: '#wrap',

    start: function () {

        const dealer = document.getElementById("dealer_id");
        const lot    = document.getElementById("lot_id");

        if (!dealer || !lot) return;

        // ---------------------------
        // RPC helper
        // ---------------------------
        async function rpc(url, params = {}) {
            try {
                const res = await fetch(url, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        jsonrpc: "2.0", method: "call",
                        params, id: Date.now(),
                    }),
                });
                const json = await res.json();
                return json.result || {};
            } catch (e) {
                console.error("RPC ERROR:", e);
                return {};
            }
        }

        function resetSelect(el, label) {
            el.innerHTML = `<option value="">Enter ${label}</option>`;
        }

        function fillLots(el, data) {
            (data || []).forEach(l => {
                el.innerHTML += `<option value="${l.id}">${l.name}</option>`;
            });
        }

        // ---------------------------
        // INITIAL LOAD
        // Serials are already scoped server-side to the logged-in user's partner
        // ---------------------------
        async function loadLots(dealer_id) {
            const params = dealer_id ? { dealer_id } : {};
            const lots = await rpc('/get_lots', params);
            resetSelect(lot, "Serial");
            fillLots(lot, lots || []);
        }

        (async function init() {
            await loadLots();
        })();

        // ---------------------------
        // DEALER CHANGE
        // Filters serials by dealer — still scoped to logged-in customer
        // Mirrors backend lot_domain: dealer_id = dealer_id AND customer_id = partner_id
        // ---------------------------
        dealer.addEventListener('change', async function () {
            const dealer_id = this.value || null;
            await loadLots(dealer_id);
        });

        // ---------------------------
        // SERIAL CHANGE
        // Auto-fills dealer from the selected lot
        // Mirrors backend _onchange_lot_id_autofill: dealer_id = lot.dealer_id
        // ---------------------------
        lot.addEventListener('change', async function () {
            const lot_id = this.value;
            if (!lot_id) { dealer.value = ''; return; }

            const res = await rpc('/get_lot_details', { lot_id });
            if (res.dealer_id) dealer.value = res.dealer_id;
        });

    },
});
