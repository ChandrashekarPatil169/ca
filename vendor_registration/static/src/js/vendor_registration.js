/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const HSN_SERVICE_URL = "https://services.gst.gov.in/commonservices/hsn/search/qsearch";

// ── Vendor Registration Form (public website page) ───────────────────────────
publicWidget.registry.VendorRegistrationForm = publicWidget.Widget.extend({
    selector: ".o_vendor_registration_form",
    events: {
        "change #country_id": "_onCountryChange",
        "input input[name='gst_number']": "_onGstInput",
        "keydown input[name='gst_number']": "_onGstKeydown",
        "input input[name='pan_number']": "_onUppercase",
        "input input[name='cin_number']": "_onUppercase",
        "input input[name='bank_ifsc']": "_onUppercase",
        "click  .o_vendor_chatbot_send": "_onChatSend",
        "keydown .o_vendor_chatbot_input": "_onChatKeydown",
        "click  .o_vendor_chatbot_launcher": "_onChatOpen",
        "click  .o_vendor_chatbot_close": "_onChatClose",
    },

    start() {
        this._filterStates(false);
        const gstInput = this.el.querySelector("input[name='gst_number']");

        if (gstInput && gstInput.value.trim().length === 15) {
            this._applyGstDetails(gstInput.value.trim().toUpperCase());
        }

        this._refreshSessionStatus().finally(() => this._initChatbot());
        return this._super(...arguments);
    },

    _onCountryChange() {
        this._filterStates(true);
    },

    _filterStates(resetState = false) {
        const countrySelect = this.el.querySelector("#country_id");
        const stateSelect = this.el.querySelector("#state_id");
        if (!countrySelect || !stateSelect) return;

        const countryId = countrySelect.value;
        stateSelect.querySelectorAll("option").forEach((option) => {
            const optionCountryId = option.dataset.countryId;
            const visible = !option.value || !countryId || optionCountryId === countryId;
            option.hidden = !visible;
            if (!visible && option.selected && resetState) {
                stateSelect.value = "";
            }
        });
    },

    _onGstInput(ev) {
        const el = ev.currentTarget;
        const pos = el.selectionStart;
        el.value = el.value.toUpperCase();
        el.setSelectionRange(pos, pos);

        const len = el.value.length;
        let hint = el.parentNode.querySelector(".gst-hint");
        if (!hint) {
            hint = document.createElement("div");
            hint.className = "form-text gst-hint";
            el.parentNode.appendChild(hint);
        }
        if (len > 0 && len < 15) {
            hint.textContent = len + " / 15 characters";
            hint.style.color = "orange";
        } else if (len === 15) {
            hint.textContent = "Fetching GST details...";
            hint.style.color = "green";
            this._applyGstDetails(el.value);
        } else {
            hint.textContent = "";
        }
    },

    _onGstKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();

            const gstNumber = ev.currentTarget.value.trim().toUpperCase();
            if (gstNumber.length === 15) {
                this._applyGstDetails(gstNumber);
            }
        }
    },

    _applyGstDetails(gstNumber) {
        const hint = this.el.querySelector(".gst-hint");
        this._applyGstinValues(this._getGstinDerivedDetails(gstNumber), false);

        fetch("/vendor-registration/gst-lookup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                id: 1,
                params: { gstin: gstNumber },
            }),
        })
        .then((response) => response.json())
        .then((data) => {
            const details = data.result || {};

            if (details.error) {
                if (hint) {
                    hint.textContent = details.error;
                    hint.style.color = "red";
                }
                return;
            }

            this._applyGstinValues(details, true);

            if (hint) {
                hint.textContent = details.name || details.legal_name
                    ? "✓ GST details fetched"
                    : "✓ GST number looks good";
                hint.style.color = "green";
            }
        })
        .catch(() => {
            if (hint) {
                hint.textContent = "✓ GST number looks good";
                hint.style.color = "green";
            }
        });
    },

    _getGstinDerivedDetails(gstNumber) {
        const stateCode = gstNumber.slice(0, 2);
        const panNumber = gstNumber.slice(2, 12);
        const panType = panNumber.slice(3, 4);
        const gstStateCodes = {
            "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
            "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
            "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
            "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
            "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
            "16": "Tripura", "17": "Meghalaya", "18": "Assam",
            "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
            "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
            "26": "Dadra and Nagar Haveli and Daman and Diu",
            "27": "Maharashtra", "29": "Karnataka", "30": "Goa",
            "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
            "34": "Puducherry", "35": "Andaman and Nicobar Islands",
            "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
        };
        const companyTypes = {
            P: "individual",
            F: "partnership",
            L: "llp",
            C: "private_ltd",
        };

        return {
            pan_number: panNumber,
            state_name: gstStateCodes[stateCode] || "",
            country_name: "India",
            company_type: companyTypes[panType] || "other",
        };
    },

    _applyGstinValues(details, allowBusinessDetails) {
        this._setInputValue("pan_number", details.pan_number);
        this._setSelectValue("company_type", details.company_type);
        this._setSelectValue("l10n_in_gst_treatment", details.l10n_in_gst_treatment);

        if (details.country_id) {
            this._setSelectValue("country_id", details.country_id);
            this._filterStates(false);
        } else if (details.country_name) {
            this._setSelectByText("#country_id", details.country_name);
            this._filterStates(false);
        }

        if (details.state_id) {
            this._setSelectValue("state_id", details.state_id);
        } else if (details.state_name) {
            this._setSelectByText("#state_id", details.state_name);
        }

        if (!allowBusinessDetails) {
            return;
        }

        this._setInputValue("name", details.name || details.legal_name, true);
        this._setInputValue("street", details.street);
        this._setInputValue("street2", details.street2);
        this._setInputValue("city", details.city);
        this._setInputValue("zip", details.zip);
        this._setInputValue("phone", details.phone);
        this._setInputValue("mobile", details.mobile);
        this._setInputValue("email", details.email);
        this._setInputValue("website", details.website);

        if (details.legal_name) {
            this._setInputValue("contact_name", details.legal_name);
        }
    },

    _setInputValue(name, value, force = false) {
        const input = this.el.querySelector(`[name='${name}']`);

        if (input && value && (force || !input.value)) {
            input.value = value;
        }
    },

    _setSelectValue(name, value) {
        const select = this.el.querySelector(`select[name='${name}']`);

        if (select && value) {
            select.value = String(value);
        }
    },

    _setSelectByText(selector, value) {
        const select = this.el.querySelector(selector);

        if (!select || !value) {
            return;
        }

        const normalize = (text) => {
            return text
                .trim()
                .toLowerCase()
                .replace(/\s*\([^)]*\)\s*/g, " ")
                .replace(/\s+/g, " ")
                .trim();
        };
        const target = normalize(value);
        const options = Array.from(select.options);
        // Prefer exact match first, then fall back to partial match
        const option =
            options.find((opt) => normalize(opt.textContent) === target) ||
            options.find((opt) => {
                const text = normalize(opt.textContent);
                return text.includes(target) || target.includes(text);
            });

        if (option) {
            select.value = option.value;
        }
    },

    _onUppercase(ev) {
        const el = ev.currentTarget;
        const pos = el.selectionStart;
        el.value = el.value.toUpperCase();
        el.setSelectionRange(pos, pos);
    },

    // ── Chatbot open/close with reset support ────────────────────────────────

    _onChatOpen(ev) {
        ev.preventDefault();
        if (this._chatNeedsReset) {
            this._resetChatbot();
        }
        this.el.classList.add("o_chatbot_open");
        this.el.classList.remove("o_chatbot_minimized");
        this._chatSetPlaceholder(this.el.querySelector(".o_vendor_chatbot_input")?.placeholder || "");
    },

    _onChatClose(ev) {
        ev.preventDefault();
        this.el.classList.add("o_chatbot_minimized");
        this.el.classList.remove("o_chatbot_open");
        this._chatNeedsReset = true;
    },

    // ── Session status check (same pattern as product_requisition) ────────────

    _refreshSessionStatus() {
        return this._jsonRpc("/vendor-registration/session-status", {})
            .then((session) => {
                if (session.authenticated) {
                    this._isAuthenticated = true;
                    // Pre-fill name and email from the logged-in user session
                    const nameInput = this.el.querySelector("input[name='name']");
                    if (nameInput && session.name && !nameInput.value) {
                        nameInput.value = session.name;
                    }
                    const contactInput = this.el.querySelector("input[name='contact_name']");
                    if (contactInput && session.name && !contactInput.value) {
                        contactInput.value = session.name;
                    }
                    const emailInput = this.el.querySelector("input[name='email']");
                    if (emailInput && session.email && !emailInput.value) {
                        emailInput.value = session.email;
                    }
                }
                return session;
            })
            .catch(() => ({}));
    },

    // ── Chatbot init & reset ─────────────────────────────────────────────────

    _initChatbot() {
        if (!this.el.querySelector(".o_vendor_chatbot")) {
            return;
        }
        this._chatStep = "name";
        this._chatNeedsReset = false;
        this.el.classList.add("o_chatbot_open");
        this.el.classList.remove("o_chatbot_minimized");
        this._chatAddBotMessage("Please enter your company or vendor name.");
        this._chatSetPlaceholder("Company / Vendor Name");
    },

    _resetChatbot() {
        const messages = this.el.querySelector(".o_vendor_chatbot_messages");
        if (messages) {
            messages.replaceChildren();
        }
        const input = this.el.querySelector(".o_vendor_chatbot_input");
        if (input) {
            input.value = "";
            input.disabled = false;
        }
        const sendButton = this.el.querySelector(".o_vendor_chatbot_send");
        if (sendButton) {
            sendButton.disabled = false;
        }
        this._chatStep = "name";
        this._chatNeedsReset = false;
        this._chatAddBotMessage("Please enter your company or vendor name.");
        this._chatSetPlaceholder("Company / Vendor Name");
    },

    // ── Chatbot message handling ─────────────────────────────────────────────

    _onChatKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this._onChatSend(ev);
        }
    },

    _onChatSend(ev) {
        ev.preventDefault();
        const input = this.el.querySelector(".o_vendor_chatbot_input");
        const value = (input?.value || "").trim();
        if (!value) {
            return;
        }
        input.value = "";
        this._chatAddUserMessage(value);
        this._handleChatValue(value);
    },

    _handleChatValue(value) {
        if (this._chatStep === "name") {
            this._chatSetField("input[name='name']", value);
            this._chatStep = "contact_name";
            this._chatAddBotMessage("Please enter the contact person name.");
            this._chatSetPlaceholder("Contact Person Name");
            return;
        }

        if (this._chatStep === "contact_name") {
            this._chatSetField("input[name='contact_name']", value);
            this._chatStep = "email";
            this._chatAddBotMessage("Please enter the email address.");
            this._chatSetPlaceholder("Email address");
            return;
        }

        if (this._chatStep === "email") {
            if (!this._isValidEmail(value)) {
                this._chatAddBotMessage("Invalid email. Please enter a valid email.");
                this._chatSetPlaceholder("Email address");
                return;
            }
            this._chatSetField("input[name='email']", value);
            this._chatStep = "phone";
            this._chatAddBotMessage("Please enter the phone number.");
            this._chatSetPlaceholder("Phone number");
            return;
        }

        if (this._chatStep === "phone") {
            this._chatSetField("input[name='phone']", value);
            this._chatStep = "gst_number";
            this._chatAddBotMessage("Enter GST number, or type Skip if not registered under GST.");
            this._chatSetPlaceholder("GST number or Skip");
            return;
        }

        if (this._chatStep === "gst_number") {
            const normalized = value.toUpperCase();
            if (!["SKIP", "NO", "NONE", "NA", "N/A"].includes(normalized)) {
                if (normalized.length !== 15) {
                    this._chatAddBotMessage("GST Number must be exactly 15 characters. Enter it again, or type Skip.");
                    this._chatSetPlaceholder("GST number or Skip");
                    return;
                }
                this._chatSetField("input[name='gst_number']", normalized);
                this._gstFetched = true;
                this._applyGstDetails(normalized);
                this._chatAddBotMessage("GST details are being fetched.");
                // Give the async fetch a moment to populate fields before asking
                setTimeout(() => {
                    this._chatAddBotMessage([
                        "Address may have been auto-filled from GST.",
                        "",
                        "1. Keep the auto-filled address",
                        "2. Enter the address manually",
                    ].join("\n"));
                    this._chatSetPlaceholder("1 = Keep GST address  |  2 = Enter manually");
                }, 1200);
                this._chatStep = "gst_address_choice";
            } else {
                this._gstFetched = false;
                this._chatStep = "street";
                this._chatAddBotMessage("Please enter street or address line 1.");
                this._chatSetPlaceholder("Street / Address Line 1");
            }
            return;
        }

        if (this._chatStep === "gst_address_choice") {
            const choice = value.trim();
            if (choice === "1") {
                this._chatAddBotMessage("Great! The auto-filled address from GST will be used.");
                this._chatStep = "additional_notes";
                this._chatAddBotMessage("Do you have any additional notes? Type your notes, or type Skip.");
                this._chatSetPlaceholder("Additional notes or Skip");
            } else if (choice === "2") {
                this._chatStep = "street";
                this._chatAddBotMessage("Please enter street or address line 1.");
                this._chatSetPlaceholder("Street / Address Line 1");
            } else {
                this._chatAddBotMessage([
                    "Please choose one option:",
                    "",
                    "1. Keep the auto-filled address",
                    "2. Enter the address manually",
                ].join("\n"));
                this._chatSetPlaceholder("1 = Keep GST address  |  2 = Enter manually");
            }
            return;
        }

        if (this._chatStep === "street") {
            this._chatSetField("input[name='street']", value);
            this._chatStep = "street2";
            this._chatAddBotMessage("Please enter address line 2.");
            this._chatSetPlaceholder("Address Line 2");
            return;
        }

        if (this._chatStep === "street2") {
            this._chatSetField("input[name='street2']", value);
            this._chatStep = "city";
            this._chatAddBotMessage("Please enter the city.");
            this._chatSetPlaceholder("City");
            return;
        }

        if (this._chatStep === "city") {
            this._chatSetField("input[name='city']", value);
            this._chatStep = "zip";
            this._chatAddBotMessage("Please enter the PIN code.");
            this._chatSetPlaceholder("PIN Code");
            return;
        }

        if (this._chatStep === "zip") {
            this._chatSetField("input[name='zip']", value);
            if (this.el.querySelector("select[name='country_id']")?.value) {
                this._chatStep = "state";
                this._chatAddBotMessage("Please enter the state.");
                this._chatSetPlaceholder("State");
            } else {
                this._chatStep = "country";
                this._chatAddBotMessage("Please enter the country.");
                this._chatSetPlaceholder("Country");
            }
            return;
        }

        if (this._chatStep === "country") {
            if (!this._chatSetSelectByText("select[name='country_id']", value)) {
                this._chatAddBotMessage("Country not found. Please enter the country exactly as shown in the form.");
                this._chatSetPlaceholder("Country");
                return;
            }
            this._filterStates(false);
            this._chatStep = "state";
            this._chatAddBotMessage("Please enter the state.");
            this._chatSetPlaceholder("State");
            return;
        }

        if (this._chatStep === "state") {
            if (!this._chatSetSelectByText("select[name='state_id']", value)) {
                this._chatAddBotMessage("State not found. Please enter the state exactly as shown in the form.");
                this._chatSetPlaceholder("State");
                return;
            }
            this._chatStep = "additional_notes";
            this._chatAddBotMessage("Do you have any additional notes? Type your notes, or type Skip.");
            this._chatSetPlaceholder("Additional notes or Skip");
            return;
        }

        if (this._chatStep === "additional_notes") {
            const normalized = value.toUpperCase();
            if (!["SKIP", "NO", "NONE", "NA", "N/A"].includes(normalized)) {
                this._chatSetField("textarea[name='description']", value);
            }
            this._chatStep = "confirm";
            this._chatAddBotMessage(this._buildConfirmationSummary());
            this._chatAddBotMessage("Type YES to confirm and submit, or NO to cancel.");
            this._chatSetPlaceholder("YES to submit  |  NO to cancel");
            return;
        }

        if (this._chatStep === "confirm") {
            const normalized = value.toUpperCase();
            if (normalized === "YES") {
                this._chatStep = "submit";
                this._chatAddBotMessage("✅ Confirmed! Submitting your registration now...");
                this._chatSetPlaceholder("Submitting...");
                this._chatDisableEntry();
                this._submitVendorRegistrationForm();
            } else if (normalized === "NO") {
                this._chatAddBotMessage("Registration cancelled. You can edit the form manually or restart the assistant.");
                this._chatDisableEntry();
            } else {
                this._chatAddBotMessage("Please type YES to confirm and submit, or NO to cancel.");
                this._chatSetPlaceholder("YES to submit  |  NO to cancel");
            }
            return;
        }
    },

    _buildConfirmationSummary() {
        const getText = (selector) => {
            const el = this.el.querySelector(selector);
            if (!el) return "";
            if (el.tagName === "SELECT") {
                return el.options[el.selectedIndex]?.text || "";
            }
            return el.value || "";
        };

        const name    = getText("input[name='name']");
        const contact = getText("input[name='contact_name']");
        const email   = getText("input[name='email']");
        const phone   = getText("input[name='phone']");
        const gst     = getText("input[name='gst_number']");
        const street  = getText("input[name='street']");
        const street2 = getText("input[name='street2']");
        const city    = getText("input[name='city']");
        const zip     = getText("input[name='zip']");
        const state   = getText("select[name='state_id']");
        const country = getText("select[name='country_id']");
        const notes   = getText("textarea[name='description']");

        const lines = ["Please review your details before submitting:", ""];
        if (name)    lines.push("• Company: " + name);
        if (contact) lines.push("• Contact: " + contact);
        if (email)   lines.push("• Email: " + email);
        if (phone)   lines.push("• Phone: " + phone);
        if (gst)     lines.push("• GST: " + gst);
        const addrParts = [street, street2, city, zip, state, country].filter(Boolean);
        if (addrParts.length) lines.push("• Address: " + addrParts.join(", "));
        if (notes)   lines.push("• Notes: " + notes);

        return lines.join("\n");
    },

    _submitVendorRegistrationForm() {
        const submitButton = this.el.querySelector("button[type='submit']");
        if (this.el.requestSubmit) {
            this.el.requestSubmit(submitButton || undefined);
        } else if (submitButton) {
            submitButton.click();
        } else {
            this.el.submit();
        }
    },

    // ── JSON RPC helper (same as product_requisition) ────────────────────────

    _jsonRpc(url, params) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                id: Date.now(),
                params,
            }),
        })
            .then((response) => response.json())
            .then((payload) => {
                if (payload.error) {
                    throw payload.error;
                }
                return payload.result || {};
            });
    },

    // ── Chatbot helpers ──────────────────────────────────────────────────────

    _chatSetField(selector, value) {
        const field = this.el.querySelector(selector);
        if (!field) {
            return;
        }
        field.value = value;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
    },

    _chatSetSelectByText(selector, value) {
        const select = this.el.querySelector(selector);
        if (!select || !value) {
            return false;
        }
        const previousValue = select.value;
        select.value = "";
        this._setSelectByText(selector, value);
        const selected = select.options[select.selectedIndex];
        if (!select.value || !selected || selected.hidden) {
            select.value = previousValue;
            return false;
        }
        select.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
    },

    _chatAddBotMessage(message) {
        this._chatAddMessage(message, "o_bot");
    },

    _chatAddUserMessage(message) {
        this._chatAddMessage(message, "o_user");
    },

    _chatAddMessage(message, className) {
        const messages = this.el.querySelector(".o_vendor_chatbot_messages");
        if (!messages) {
            return;
        }
        const item = document.createElement("div");
        item.className = `o_vendor_chatbot_message ${className}`;
        item.textContent = message;
        messages.appendChild(item);
        messages.scrollTop = messages.scrollHeight;
    },

    _chatSetPlaceholder(placeholder) {
        const input = this.el.querySelector(".o_vendor_chatbot_input");
        if (input) {
            input.placeholder = placeholder || "";
            input.focus();
        }
    },

    _chatDisableEntry() {
        const input = this.el.querySelector(".o_vendor_chatbot_input");
        if (input) {
            input.disabled = true;
        }
        const sendButton = this.el.querySelector(".o_vendor_chatbot_send");
        if (sendButton) {
            sendButton.disabled = true;
        }
    },

    _isValidEmail(email) {
        return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email || "");
    },
});

// ── Vendor Product Submission Form (portal page) ──────────────────────────────
publicWidget.registry.VendorProductForm = publicWidget.Widget.extend({
    selector: ".o_vendor_product_form",
    events: {
        "input #product-name-input":  "_onProductInput",
        "input #hsn-code-input":      "_onHsnInput",
        "click .vp-suggestion-item":  "_onSuggestionClick",
        "click .vp-none-item":        "_onNoneClick",
        "click .hsn-suggestion-item": "_onHsnSuggestionClick",
        "click #clear-product-match": "_onClearMatch",
    },

    start() {
        this._debounceTimer = null;
        this._hsnDebounceTimer = null;
        this._isMatchSelected = false;

        // Close suggestions when clicking outside
        this._outsideClickHandler = this._onOutsideClick.bind(this);
        document.addEventListener("click", this._outsideClickHandler);

        return this._super(...arguments);
    },

    destroy() {
        document.removeEventListener("click", this._outsideClickHandler);
        this._super(...arguments);
    },

    _onProductInput(ev) {
        const query = ev.currentTarget.value.trim();

        // If user edits after a match, reset
        if (this._isMatchSelected) {
            this._clearMatch(false);
        }

        clearTimeout(this._debounceTimer);

        const suggestionsBox = this.el.querySelector("#product-suggestions");
        const newInfo = this.el.querySelector("#product-new-info");

        if (query.length < 2) {
            suggestionsBox.style.display = "none";
            if (newInfo) newInfo.style.display = "none";
            return;
        }

        this._debounceTimer = setTimeout(() => {
            fetch("/my/vendor-products/search-products", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0", method: "call", id: 1,
                    params: { query },
                }),
            })
            .then((r) => r.json())
            .then((data) => {
                this._renderSuggestions(data.result || [], query);
            })
            .catch(() => {
                suggestionsBox.style.display = "none";
            });
        }, 300);
    },

    _renderSuggestions(products, query) {
        const box = this.el.querySelector("#product-suggestions");
        const newInfo = this.el.querySelector("#product-new-info");
        box.innerHTML = "";

        const typeLabel = { product: "Storable", consu: "Consumable", service: "Service" };

        products.forEach((p) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "list-group-item list-group-item-action d-flex justify-content-between align-items-center vp-suggestion-item";
            btn.dataset.productId = p.id;
            btn.dataset.productName = p.name;
            btn.dataset.hsnCode = p.l10n_in_hsn_code || "";
            btn.dataset.uom = p.uom || "";
            btn.dataset.price = p.price || "";
            btn.innerHTML = `<span>${this._escapeHtml(p.name)}</span><small class="text-muted ms-2">${this._escapeHtml(typeLabel[p.type] || p.type || "")}</small>`;
            box.appendChild(btn);
        });

        // "None of these" option
        const noneBtn = document.createElement("button");
        noneBtn.type = "button";
        noneBtn.className = "list-group-item list-group-item-action fst-italic text-secondary vp-none-item";
        noneBtn.textContent = products.length
            ? "+ None of these – submit as a new product"
            : "+ No match found – submit as a new product";
        box.appendChild(noneBtn);

        box.style.display = "block";

        if (newInfo) {
            newInfo.style.display = products.length === 0 ? "block" : "none";
        }
    },

    _onSuggestionClick(ev) {
        const btn = ev.currentTarget;
        const productId = btn.dataset.productId;
        const productName = btn.dataset.productName;

        const nameInput = this.el.querySelector("#product-name-input");
        const hiddenInput = this.el.querySelector("#existing_product_tmpl_id");
        const hsnInput = this.el.querySelector("#hsn-code-input");
        const uomInput = this.el.querySelector("input[name='uom']");
        const priceInput = this.el.querySelector("input[name='price']");
        const matchInfo = this.el.querySelector("#product-match-info");
        const newInfo = this.el.querySelector("#product-new-info");
        const box = this.el.querySelector("#product-suggestions");

        if (nameInput) nameInput.value = productName;
        if (hiddenInput) hiddenInput.value = productId;
        if (hsnInput && btn.dataset.hsnCode) hsnInput.value = btn.dataset.hsnCode;
        if (uomInput && btn.dataset.uom) uomInput.value = btn.dataset.uom;
        if (priceInput && btn.dataset.price) priceInput.value = btn.dataset.price;
        this._isMatchSelected = true;
        if (box) box.style.display = "none";
        if (matchInfo) matchInfo.style.display = "block";
        if (newInfo) newInfo.style.display = "none";
    },

    _onNoneClick() {
        this._clearMatch(true);
        const box = this.el.querySelector("#product-suggestions");
        if (box) box.style.display = "none";
    },

    _onClearMatch(ev) {
        ev.preventDefault();
        this._clearMatch(true);
        const nameInput = this.el.querySelector("#product-name-input");
        if (nameInput) {
            nameInput.value = "";
            nameInput.focus();
        }
    },

    _clearMatch(showNewInfo) {
        const hiddenInput = this.el.querySelector("#existing_product_tmpl_id");
        const matchInfo = this.el.querySelector("#product-match-info");
        const newInfo = this.el.querySelector("#product-new-info");
        const nameInput = this.el.querySelector("#product-name-input");

        if (hiddenInput) hiddenInput.value = "";
        this._isMatchSelected = false;
        if (matchInfo) matchInfo.style.display = "none";
        if (newInfo) newInfo.style.display = showNewInfo && nameInput && nameInput.value.trim().length >= 2 ? "block" : "none";
    },

    _onHsnInput(ev) {
        const query = ev.currentTarget.value.trim();
        const suggestionsBox = this.el.querySelector("#hsn-suggestions");

        clearTimeout(this._hsnDebounceTimer);

        if (!suggestionsBox || query.length < 3) {
            if (suggestionsBox) suggestionsBox.style.display = "none";
            return;
        }

        this._hsnDebounceTimer = setTimeout(() => {
            const productType = this.el.querySelector("select[name='product_type']")?.value || "goods";
            this._fetchHsnSuggestions(query, productType)
            .then((items) => this._renderHsnSuggestions(items))
            .catch(() => {
                suggestionsBox.style.display = "none";
            });
        }, 350);
    },

    _fetchHsnSuggestions(query, productType) {
        const onlyDigits = /^\d+$/.test(query);
        const requests = onlyDigits
            ? [{ selectedType: "byCode", category: "null" }]
            : [{ selectedType: "byDesc", category: productType === "service" ? "S" : "P" }];

        return Promise.all(requests.map((requestParams) => {
            const params = new URLSearchParams({
                inputText: query,
                selectedType: requestParams.selectedType,
                category: requestParams.category,
            });

            return fetch(`${HSN_SERVICE_URL}?${params.toString()}`)
                .then((response) => response.ok ? response.json() : { data: [] });
        })).then((responses) => {
            const suggestions = [];

            responses.forEach((response) => {
                (response.data || []).forEach((item) => {
                    if (item.c && item.c.length > 3) {
                        suggestions.push({
                            code: item.c,
                            description: item.n || "",
                        });
                    }
                });
            });

            return suggestions.slice(0, 10);
        });
    },

    _renderHsnSuggestions(items) {
        const box = this.el.querySelector("#hsn-suggestions");
        if (!box) return;

        box.innerHTML = "";

        if (!items.length) {
            box.style.display = "none";
            return;
        }

        items.forEach((item) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "list-group-item list-group-item-action hsn-suggestion-item";
            btn.dataset.code = item.code;
            btn.innerHTML = `<strong>${this._escapeHtml(item.code)}</strong><br/><small class="text-muted">${this._escapeHtml(item.description || "")}</small>`;
            box.appendChild(btn);
        });

        box.style.display = "block";
    },

    _onHsnSuggestionClick(ev) {
        const input = this.el.querySelector("#hsn-code-input");
        const box = this.el.querySelector("#hsn-suggestions");

        if (input) input.value = ev.currentTarget.dataset.code || "";
        if (box) box.style.display = "none";
    },

    _onOutsideClick(ev) {
        const nameInput = this.el.querySelector("#product-name-input");
        const box = this.el.querySelector("#product-suggestions");
        const hsnBox = this.el.querySelector("#hsn-suggestions");
        if (!this.el.contains(ev.target)) {
            if (box) box.style.display = "none";
            if (hsnBox) hsnBox.style.display = "none";
        }
    },

    _escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value || "";
        return div.innerHTML;
    },
});
