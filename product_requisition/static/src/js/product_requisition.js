/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.ProductRequisitionForm = publicWidget.Widget.extend({
    selector: ".o_product_requisition_form",
    events: {
        "submit":                              "_onSubmit",
        "click  .o_send_requisition_otp":      "_onSendOtp",
        "click  .o_resend_requisition_otp":    "_onSendOtp",
        "click  .o_verify_requisition_otp":    "_onVerifyOtp",
        "input  .o_req_email":                 "_onEmailInput",
        "click  .o_add_requisition_line":    "_onAddLine",
        "click  .o_remove_requisition_line": "_onRemoveLine",
        "input  .o_req_product_select":      "_onProductChange",
        "change .o_req_product_select":      "_onProductChange",
        "change .o_req_product_dropdown":    "_onProductDropdownChange",
        "change .o_req_product_category":     "_onLineFilterChange",
        "change .o_req_asset_category":       "_onLineFilterChange",
        "input  .o_req_quantity":            "_onQuantityInput",
        "change #country_id":                "_onCountryChange",
        "click  .o_requisition_chatbot_send": "_onChatSend",
        "keydown .o_requisition_chatbot_input": "_onChatKeydown",
        "click  .o_requisition_chatbot_launcher": "_onChatOpen",
        "click  .o_requisition_chatbot_close": "_onChatClose",
    },

    start() {
        this._filterStates();
        this._otpVerified = this.el.dataset.otpVerified === "1";
        this._otpRequired = this.el.dataset.otpRequired === "1";
        this._isAuthenticated = false;
        this._cacheProductOptions();
        this._loadCatalog();
        this._setProductsEnabled(this._otpVerified);
        this.el.querySelectorAll(".o_product_requisition_line").forEach((row) => this._syncLineFilters(row));
        this._refreshSessionStatus().finally(() => this._initChatbot());
        return this._super(...arguments);
    },

    _onSubmit(ev) {
        if (this._otpRequired && !this._otpVerified) {
            ev.preventDefault();
            this._setOtpStatus("Please verify your email with OTP before submitting.", "danger");
        }
    },

    _onSendOtp(ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        const name = this.el.querySelector("#customer_name")?.value.trim() || "";
        const email = this.el.querySelector("#email")?.value.trim() || "";
        const code = this.el.querySelector("#employee_code")?.value.trim() || "";

        if (!name || !email) {
            this._setOtpStatus("Please enter full name and email before sending OTP.", "danger");
            return;
        }

        this._otpVerified = false;
        this.el.dataset.otpVerified = "0";
        const tokenInput = this.el.querySelector(".o_req_otp_token");
        if (tokenInput) tokenInput.value = "";
        this._setProductsEnabled(false);
        this._setButtonLoading(button, true);
        this._jsonRpc("/product-requisition/send-otp", { name, email, code })
            .then((result) => {
                this._setOtpStatus(result.message, result.ok ? "success" : "danger");
                if (result.ok) {
                    const area = this.el.querySelector(".o_otp_verify_area");
                    if (area) area.style.display = "";
                    const otpInput = this.el.querySelector(".o_req_otp");
                    if (otpInput) otpInput.focus();
                }
            })
            .catch((error) => this._setOtpStatus(this._getRpcErrorMessage(error, "OTP request failed. Please try again."), "danger"))
            .finally(() => this._setButtonLoading(button, false));
    },

    _onVerifyOtp(ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        const email = this.el.querySelector("#email")?.value.trim() || "";
        const otp = this.el.querySelector(".o_req_otp")?.value.trim() || "";

        this._setButtonLoading(button, true);
        this._jsonRpc("/product-requisition/verify-otp", { email, otp })
            .then((result) => {
                this._setOtpStatus(result.message, result.ok ? "success" : "danger");
                if (result.ok) {
                    this._otpVerified = true;
                    this.el.dataset.otpVerified = "1";
                    const tokenInput = this.el.querySelector(".o_req_otp_token");
                    if (tokenInput) tokenInput.value = result.token || "";
                    this._setProductsEnabled(true);
                    const area = this.el.querySelector(".o_otp_verify_area");
                    if (area) area.style.display = "none";
                    if (this.el.querySelector(".o_requisition_chatbot_messages")) {
                        this._chatStep = "product_type";
                        this._chatAddBotMessage("Email verified.");
                        this._chatAskProductType();
                    }
                }
            })
            .catch((error) => this._setOtpStatus(this._getRpcErrorMessage(error, "OTP verification failed. Please try again."), "danger"))
            .finally(() => this._setButtonLoading(button, false));
    },

    _onEmailInput() {
        if (!this._otpRequired) return;
        if (!this._otpVerified) return;
        this._otpVerified = false;
        this.el.dataset.otpVerified = "0";
        const tokenInput = this.el.querySelector(".o_req_otp_token");
        if (tokenInput) tokenInput.value = "";
        this._setProductsEnabled(false);
        const area = this.el.querySelector(".o_otp_verify_area");
        if (area) area.style.display = "";
        this._setOtpStatus("Please send and verify OTP for this email.", "info");
    },

    _onAddLine(ev) {
        ev.preventDefault();
        const tbody  = this.el.querySelector(".o_product_requisition_lines tbody");
        if (!tbody) {
            return;
        }
        const source = tbody.querySelector(".o_product_requisition_line");
        if (!source) {
            return;
        }
        const clone  = source.cloneNode(true);
        clone.querySelectorAll("datalist").forEach((list) => list.remove());
        clone.querySelectorAll("select, input").forEach((field) => {
            if (field.tagName === "SELECT") {
                field.selectedIndex = 0;
            } else if (field.classList.contains("o_req_quantity")) {
                field.value = "1";
            } else {
                field.value = "";
            }
        });

        // Safely clear display spans on the cloned row
        const unitEl = clone.querySelector(".o_req_unit_price");
        const subEl  = clone.querySelector(".o_req_subtotal");
        if (unitEl) unitEl.textContent = "";
        if (subEl)  subEl.textContent  = "";

        tbody.appendChild(clone);
        this._syncLineFilters(clone);
        this._updateTotal();
    },

    _onRemoveLine(ev) {
        ev.preventDefault();
        const rows = this.el.querySelectorAll(".o_product_requisition_line");
        if (rows.length > 1) {
            ev.currentTarget.closest(".o_product_requisition_line").remove();
            this._syncProductColumns();
            this._updateTotal();
        }
    },

    _onProductChange(ev) {
        const input = ev.currentTarget;
        const row = input.closest(".o_product_requisition_line");
        const option = this._getProductOption(input);
        const productIdEl = row?.querySelector(".o_req_product_id");
        if (productIdEl) {
            productIdEl.value = option ? option.productId || "" : "";
        }
        const dropdown = row?.querySelector(".o_req_product_dropdown");
        if (dropdown) {
            dropdown.value = option ? option.productId || "" : "";
        }
        const uomEl = row?.querySelector(".o_req_uom");
        if (uomEl && option && !uomEl.value) {
            uomEl.value = option.uom || "";
        }
        if (!option) {
            this._setSubtotal(row, 0);
            this._updateTotal();
            return;
        }
        const price  = parseFloat(option.price || "0");
        const qtyEl  = row ? row.querySelector(".o_req_quantity") : null;
        const qty    = qtyEl ? (parseFloat(qtyEl.value) || 1) : 1;

        const priceEl = row ? row.querySelector(".o_req_unit_price") : null;
        if (priceEl) priceEl.textContent = price > 0 ? this._fmt(price) : "";

        this._setSubtotal(row, price * qty);
        this._updateTotal();
    },

    _onProductDropdownChange(ev) {
        const dropdown = ev.currentTarget;
        const row = dropdown.closest(".o_product_requisition_line");
        const input = row?.querySelector(".o_req_product_select");
        const option = this._getProductOptionById(dropdown.value, row);
        if (input) {
            input.value = option ? option.value : "";
            this._onProductChange({ currentTarget: input });
        }
    },

    _onLineFilterChange(ev) {
        const row = ev.currentTarget.closest(".o_product_requisition_line");
        this._syncLineFilters(row, true);
    },

    _onQuantityInput(ev) {
        const qtyEl  = ev.currentTarget;
        const row    = qtyEl.closest(".o_product_requisition_line");
        const input = row ? row.querySelector(".o_req_product_select") : null;
        if (!input) return;
        const option = this._getProductOption(input);
        if (!option) return;
        const price  = parseFloat(option.price || "0");
        const qty    = parseFloat(qtyEl.value) || 0;
        this._setSubtotal(row, price * qty);
        this._updateTotal();
    },

    _onCountryChange() {
        this._filterStates(true);
    },

    _onChatOpen(ev) {
        ev.preventDefault();
        if (this._chatNeedsReset) {
            this._resetChatbot();
        }
        this.el.classList.add("o_chatbot_open");
        this.el.classList.remove("o_chatbot_minimized");
        this._chatSetPlaceholder(this.el.querySelector(".o_requisition_chatbot_input")?.placeholder || "");
    },

    _onChatClose(ev) {
        ev.preventDefault();
        this.el.classList.add("o_chatbot_minimized");
        this.el.classList.remove("o_chatbot_open");
        this._chatNeedsReset = true;
    },

    _initChatbot() {
        this._chatStep = this._otpRequired ? "name" : "product_type";
        this._chatProductOption = null;
        this._chatCurrentLine = this._getPrimaryChatLine();
        this._chatProductCount = 0;
        this.el.classList.add("o_chatbot_open");
        this.el.classList.remove("o_chatbot_minimized");
        if (this._otpRequired) {
            this._chatAddBotMessage("Please enter your full name.");
            this._chatSetPlaceholder("Full name");
        } else {
            this._chatAskProductType();
        }
        this._chatNeedsReset = false;
    },

    _resetChatbot() {
        const messages = this.el.querySelector(".o_requisition_chatbot_messages");
        if (messages) {
            messages.replaceChildren();
        }
        const input = this.el.querySelector(".o_requisition_chatbot_input");
        if (input) {
            input.value = "";
            input.disabled = false;
        }
        const sendButton = this.el.querySelector(".o_requisition_chatbot_send");
        if (sendButton) {
            sendButton.disabled = false;
        }
        this._chatStep = this._otpRequired ? "name" : "product_type";
        this._chatProductOption = null;
        this._chatCurrentLine = this._getPrimaryChatLine();
        this._chatProductCount = this._getChatProductCount();
        this._chatNeedsReset = false;
        if (this._otpRequired) {
            this._chatAddBotMessage("Please enter your full name.");
            this._chatSetPlaceholder("Full name");
        } else {
            this._chatAskProductType();
        }
    },

    _onChatKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this._onChatSend(ev);
        }
    },

    _onChatSend(ev) {
        ev.preventDefault();
        const input = this.el.querySelector(".o_requisition_chatbot_input");
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
            this._chatSetField("#customer_name", value);
            this._chatStep = "email";
            this._chatAddBotMessage("Please enter your email.");
            this._chatSetPlaceholder("Email address");
            return;
        }

        if (this._chatStep === "email") {
            if (!this._isValidEmail(value)) {
                this._setOtpStatus("Please enter a valid email address.", "danger");
                this._chatAddBotMessage("Invalid email. Please enter a valid email.");
                this._chatSetPlaceholder("Email address");
                return;
            }
            this._chatSetField("#email", value);
            this._chatSendOtp();
            return;
        }

        if (this._chatStep === "otp") {
            this._chatSetField(".o_req_otp", value);
            this._chatVerifyOtp();
            return;
        }

        if (this._chatStep === "product_type") {
            if (value === "1") {
                this._chatSetProductType("goods");
                this._chatStep = "product_action";
                this._chatAskProductAction();
                return;
            }
            if (value === "2") {
                this._chatSetProductType("service");
                this._chatStep = "product_action";
                this._chatAskProductAction();
                return;
            }
            this._chatAddBotMessage("Please select a valid product type.\n1. Goods\n2. Service\n\nEnter 1 or 2.");
            this._chatSetPlaceholder("1 or 2");
            return;
        }

        if (this._chatStep === "product_action") {
            if (value === "1") {
                this._chatStep = "product";
                this._chatAddBotMessage("Please enter the product.");
                this._chatSetPlaceholder("Product name");
                return;
            }
            if (value === "2" || this._isChatExit(value)) {
                if (this._getChatProductCount()) {
                    this._chatStep = "submit";
                    this._chatAddBotMessage("Submitting the added products.");
                    this._disableChatInput("Submitting");
                    this._submitRequisitionForm();
                } else {
                    this._chatEndConversation("The conversation has been closed.");
                }
                return;
            }
            this._chatAddBotMessage("Please select an option.\n1. Add product\n2. Exit\n\nEnter 1 or 2.");
            this._chatSetPlaceholder("1 or 2");
            return;
        }

        if (this._chatStep === "product") {
            if (!this._isValidProductText(value)) {
                this._chatAddBotMessage("Invalid product. Please enter a valid product.");
                this._chatSetPlaceholder("Product name");
                return;
            }
            const option = this._findChatProductOption(value);
            this._chatProductOption = option;
            if (option) {
                this._chatApplyProduct(option);
            } else {
                this._chatApplyProductName(value);
            }
            this._chatStep = "quantity";
            this._chatAddBotMessage("Please enter the quantity.");
            this._chatSetPlaceholder("Quantity");
            return;
        }

        if (this._chatStep === "quantity") {
            const quantity = parseFloat(value);
            if (!Number.isFinite(quantity) || quantity <= 0) {
                this._chatAddBotMessage("Please enter a valid quantity.");
                this._chatSetPlaceholder("Quantity");
                return;
            }
            const row = this._getPrimaryChatLine();
            this._chatSetField(".o_req_quantity", String(quantity), row);
            this._chatStep = "budget";
            this._chatAddBotMessage("Please enter the budget.");
            this._chatSetPlaceholder("Budget");
            return;
        }

        if (this._chatStep === "budget") {
            const budget = parseFloat(value);
            if (!Number.isFinite(budget) || budget < 0) {
                this._chatAddBotMessage("Please enter a valid budget.");
                this._chatSetPlaceholder("Budget");
                return;
            }
            const row = this._getPrimaryChatLine();
            this._chatSetField("input[name='budget']", String(budget), row);
            this._chatProductCount = this._getChatProductCount();
            this._chatStep = "continue";
            this._chatAddBotMessage("To continue adding products, please select an option.\n1. Add another product\n2. Submit added products\n\nEnter 1 or 2.");
            this._chatSetPlaceholder("1 or 2");
            return;
        }

        if (this._chatStep === "continue") {
            if (value === "1") {
                this._chatCurrentLine = this._createChatLine();
                this._chatProductOption = null;
                this._chatStep = "product_type";
                this._chatAskProductType();
                return;
            }
            if (value === "2") {
                if (!this._getChatProductCount()) {
                    this._chatAddBotMessage("Please add at least one product before submitting.");
                    this._chatStep = "product_type";
                    this._chatAskProductType();
                    return;
                }
                this._chatStep = "submit";
                this._chatAddBotMessage("Submitting the added products.");
                this._disableChatInput("Submitting");
                this._submitRequisitionForm();
                return;
            }
            this._chatAddBotMessage("Please select an option.\n1. Add another product\n2. Submit added products\n\nEnter 1 or 2.");
            this._chatSetPlaceholder("1 or 2");
        }
    },

    _submitRequisitionForm() {
        if (this._chatSubmitting) {
            return;
        }
        if (!this._getChatProductCount()) {
            this._chatEndConversation("The conversation has been closed.");
            return;
        }
        this._chatSubmitting = true;
        this._setProductsEnabled(true);
        this.el.querySelectorAll(".o_product_requisition_line input, .o_product_requisition_line select, .o_product_requisition_line textarea")
            .forEach((field) => {
                field.disabled = false;
            });
        window.setTimeout(() => {
            HTMLFormElement.prototype.submit.call(this.el);
        }, 0);
    },

    _chatSendOtp() {
        const button = this.el.querySelector(".o_send_requisition_otp");
        this._chatAddBotMessage("Sending OTP to your email...");
        this._sendOtp(button)
            .then((result) => {
                if (result.ok) {
                    this._chatStep = "otp";
                    this._chatAddBotMessage("OTP sent. Please enter the OTP.");
                    this._chatSetPlaceholder("6 digit OTP");
                } else {
                    this._chatStep = "email";
                    this._chatAddBotMessage(result.message || "OTP could not be sent. Please enter your email again.");
                    this._chatSetPlaceholder("Email address");
                }
            });
    },

    _chatVerifyOtp() {
        const button = this.el.querySelector(".o_verify_requisition_otp");
        this._chatAddBotMessage("Verifying OTP...");
        this._verifyOtp(button)
            .then((result) => {
                if (result.ok) {
                    this._chatStep = "product_type";
                    this._chatAddBotMessage("Email verified.");
                    this._chatAskProductType();
                } else {
                    this._chatStep = "otp";
                    this._chatAddBotMessage(result.message || "OTP verification failed. Please try again.");
                    this._chatSetPlaceholder("6 digit OTP");
                }
            });
    },

    _chatAskProductType() {
        this._chatAddBotMessage("Please enter the product type.\n1. Goods\n2. Service\n\nEnter 1 or 2.");
        this._chatSetPlaceholder("1 or 2");
    },

    _chatAskProductAction() {
        this._chatAddBotMessage("Please enter the product.\n1. Add product\n2. Exit\n\nEnter 1 or 2.");
        this._chatSetPlaceholder("1 or 2");
    },

    _chatSetProductType(productType) {
        const row = this._getPrimaryChatLine();
        const categoryEl = row?.querySelector(".o_req_product_category");
        if (categoryEl) {
            categoryEl.value = productType;
            categoryEl.dispatchEvent(new Event("change", { bubbles: true }));
        }
    },

    _chatApplyProduct(option) {
        const row = this._getPrimaryChatLine();
        const categoryEl = row?.querySelector(".o_req_product_category");
        if (categoryEl) {
            categoryEl.value = option.productCategory || categoryEl.value || "goods";
            categoryEl.dispatchEvent(new Event("change", { bubbles: true }));
        }
        const input = row?.querySelector(".o_req_product_select");
        const productIdEl = row?.querySelector(".o_req_product_id");
        const dropdown = row?.querySelector(".o_req_product_dropdown");
        if (input) {
            input.value = option.value;
        }
        if (productIdEl) {
            productIdEl.value = option.productId || "";
        }
        if (dropdown) {
            dropdown.value = option.productId || "";
        }
        if (input) {
            this._onProductChange({ currentTarget: input });
        }
    },

    _chatApplyProductName(productName) {
        const row = this._getPrimaryChatLine();
        const categoryEl = row?.querySelector(".o_req_product_category");
        if (categoryEl) {
            categoryEl.value = categoryEl.value || "goods";
            categoryEl.dispatchEvent(new Event("change", { bubbles: true }));
        }
        const input = row?.querySelector(".o_req_product_select");
        const productIdEl = row?.querySelector(".o_req_product_id");
        const dropdown = row?.querySelector(".o_req_product_dropdown");
        if (input) {
            input.value = productName;
        }
        if (productIdEl) {
            productIdEl.value = "";
        }
        if (dropdown) {
            dropdown.value = "";
        }
    },

    _findChatProductOption(value) {
        const search = value.toLowerCase();
        const row = this._getPrimaryChatLine();
        const category = row?.querySelector(".o_req_product_category")?.value || "goods";
        const options = this._allProductOptions || [];
        const filteredOptions = options.filter((option) => option.productCategory === category);
        return filteredOptions.find((option) => option.value.toLowerCase() === search)
            || filteredOptions.find((option) => option.value.toLowerCase().includes(search));
    },

    _getPrimaryChatLine() {
        if (this._chatCurrentLine?.isConnected) {
            return this._chatCurrentLine;
        }
        this._chatCurrentLine = this.el.querySelector(".o_product_requisition_line");
        return this._chatCurrentLine;
    },

    _createChatLine() {
        const rows = Array.from(this.el.querySelectorAll(".o_product_requisition_line"));
        const source = rows[rows.length - 1] || this._getPrimaryChatLine();
        if (!source) {
            return null;
        }
        const clone = source.cloneNode(true);
        clone.querySelectorAll("datalist").forEach((list) => list.remove());
        clone.querySelectorAll("select, input").forEach((field) => {
            if (field.tagName === "SELECT") {
                field.selectedIndex = 0;
            } else if (field.classList.contains("o_req_quantity")) {
                field.value = "1";
            } else {
                field.value = "";
            }
            field.disabled = false;
        });
        const unitEl = clone.querySelector(".o_req_unit_price");
        const subEl = clone.querySelector(".o_req_subtotal");
        if (unitEl) unitEl.textContent = "";
        if (subEl) subEl.textContent = "";

        const tbody = this.el.querySelector(".o_product_requisition_lines tbody");
        if (tbody) {
            tbody.appendChild(clone);
        } else {
            const submitButton = this.el.querySelector(".o_submit_requisition");
            source.parentNode.insertBefore(clone, submitButton || null);
        }
        this._syncLineFilters(clone, true);
        this._updateTotal();
        return clone;
    },

    _getChatProductCount() {
        return Array.from(this.el.querySelectorAll(".o_product_requisition_line"))
            .filter((row) => row.querySelector(".o_req_product_select")?.value.trim())
            .length;
    },

    _isChatExit(value) {
        return ["exit", "quit", "close"].includes((value || "").trim().toLowerCase());
    },

    _disableChatInput(placeholder = "") {
        const input = this.el.querySelector(".o_requisition_chatbot_input");
        if (input) {
            input.disabled = true;
            input.placeholder = placeholder;
        }
        const sendButton = this.el.querySelector(".o_requisition_chatbot_send");
        if (sendButton) {
            sendButton.disabled = true;
        }
    },

    _chatEndConversation(message) {
        this._chatStep = "closed";
        this._chatAddBotMessage(message);
        this._disableChatInput("Closed");
        window.setTimeout(() => {
            this.el.classList.add("o_chatbot_minimized");
            this.el.classList.remove("o_chatbot_open");
            this._chatNeedsReset = true;
        }, 700);
    },

    _chatSetField(selector, value, root = this.el) {
        const field = root?.querySelector(selector);
        if (!field) {
            return;
        }
        field.value = value;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
    },

    _chatAddBotMessage(message) {
        this._chatAddMessage(message, "o_bot");
    },

    _chatAddUserMessage(message) {
        this._chatAddMessage(message, "o_user");
    },

    _chatAddMessage(message, className) {
        const messages = this.el.querySelector(".o_requisition_chatbot_messages");
        if (!messages) {
            return;
        }
        const item = document.createElement("div");
        item.className = `o_requisition_chatbot_message ${className}`;
        item.textContent = message;
        messages.appendChild(item);
        messages.scrollTop = messages.scrollHeight;
    },

    _chatSetPlaceholder(placeholder) {
        const input = this.el.querySelector(".o_requisition_chatbot_input");
        if (input) {
            input.placeholder = placeholder || "";
            input.focus();
        }
    },

    _isValidEmail(email) {
        return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email || "");
    },

    _isValidProductText(productName) {
        return /[A-Za-z]/.test(productName || "");
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

    _setSubtotal(row, value) {
        if (!row) return;
        const el = row.querySelector(".o_req_subtotal");
        if (el) el.textContent = value > 0 ? this._fmt(value) : "";
    },

    _setProductsEnabled(enabled) {
        const fieldset = this.el.querySelector(".o_requisition_products_fieldset");
        if (fieldset) {
            fieldset.disabled = !enabled;
        }
    },

    _refreshSessionStatus() {
        return this._jsonRpc("/product-requisition/session-status", {})
            .then((session) => {
                if (session.authenticated) {
                    this._isAuthenticated = true;
                    this._otpRequired = false;
                    this._otpVerified = true;
                    this.el.dataset.otpRequired = "0";
                    this.el.dataset.otpVerified = "1";
                    this._setProductsEnabled(true);
                    this.el.querySelectorAll(".o_send_requisition_otp, .o_resend_requisition_otp").forEach((button) => {
                        button.style.display = "none";
                    });
                    const area = this.el.querySelector(".o_otp_verify_area");
                    if (area) area.style.display = "none";
                    const nameInput = this.el.querySelector("#customer_name");
                    if (nameInput && session.name) nameInput.value = session.name;
                    const emailInput = this.el.querySelector("#email");
                    if (emailInput && session.email) emailInput.value = session.email;
                    this._setOtpStatus("Signed in. Product details are active.", "success");
                }
                return session;
            })
            .catch(() => ({}));
    },

    _setOtpStatus(message, type) {
        const status = this.el.querySelector(".o_req_otp_status");
        if (!status) return;
        status.textContent = message || "";
        status.className = `alert mb-0 py-2 o_req_otp_status alert-${type || "info"}`;
    },

    _setButtonLoading(button, loading) {
        if (!button) return;
        if (loading) {
            button.dataset.originalText = button.textContent;
            button.disabled = true;
            button.textContent = "Please wait...";
        } else {
            button.disabled = false;
            button.textContent = button.dataset.originalText || button.textContent;
        }
    },

    _sendOtp(button) {
        const name = this.el.querySelector("#customer_name")?.value.trim() || "";
        const email = this.el.querySelector("#email")?.value.trim() || "";
        const code = this.el.querySelector("#employee_code")?.value.trim() || "";

        if (!name || !email) {
            this._setOtpStatus("Please enter full name and email before sending OTP.", "danger");
            return Promise.resolve({ ok: false, message: "Please enter full name and email before sending OTP." });
        }

        this._otpVerified = false;
        this.el.dataset.otpVerified = "0";
        const tokenInput = this.el.querySelector(".o_req_otp_token");
        if (tokenInput) tokenInput.value = "";
        this._setProductsEnabled(false);
        this._setButtonLoading(button, true);
        return this._jsonRpc("/product-requisition/send-otp", { name, email, code })
            .then((result) => {
                this._setOtpStatus(result.message, result.ok ? "success" : "danger");
                if (result.ok) {
                    const area = this.el.querySelector(".o_otp_verify_area");
                    if (area) area.style.display = "";
                    const otpInput = this.el.querySelector(".o_req_otp");
                    if (otpInput) otpInput.focus();
                }
                return result;
            })
            .catch((error) => {
                const message = this._getRpcErrorMessage(error, "OTP request failed. Please try again.");
                this._setOtpStatus(message, "danger");
                return { ok: false, message };
            })
            .finally(() => this._setButtonLoading(button, false));
    },

    _verifyOtp(button) {
        const email = this.el.querySelector("#email")?.value.trim() || "";
        const otp = this.el.querySelector(".o_req_otp")?.value.trim() || "";

        this._setButtonLoading(button, true);
        return this._jsonRpc("/product-requisition/verify-otp", { email, otp })
            .then((result) => {
                this._setOtpStatus(result.message, result.ok ? "success" : "danger");
                if (result.ok) {
                    this._otpVerified = true;
                    this.el.dataset.otpVerified = "1";
                    const tokenInput = this.el.querySelector(".o_req_otp_token");
                    if (tokenInput) tokenInput.value = result.token || "";
                    this._setProductsEnabled(true);
                    const area = this.el.querySelector(".o_otp_verify_area");
                    if (area) area.style.display = "none";
                }
                return result;
            })
            .catch((error) => {
                const message = this._getRpcErrorMessage(error, "OTP verification failed. Please try again.");
                this._setOtpStatus(message, "danger");
                return { ok: false, message };
            })
            .finally(() => this._setButtonLoading(button, false));
    },

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

    _loadCatalog() {
        this._jsonRpc("/product-requisition/catalog", {})
            .then((catalog) => {
                const categories = catalog.categories || [];
                const products = catalog.products || [];
                this._allProductOptions = products.map((product) => ({
                    value: product.name,
                    productId: String(product.id || ""),
                    productCategory: product.product_category || "goods",
                    assetCategoryIds: (product.asset_category_ids || []).map((id) => String(id)),
                    uom: product.uom || "",
                    price: String(product.price || "0"),
                }));
                if (Array.isArray(categories) && categories.length) {
                    this.el.querySelectorAll(".o_req_asset_category").forEach((select) => {
                        const currentValue = select.value;
                        select.innerHTML = "";
                        select.appendChild(new Option("Select asset", ""));
                        categories.forEach((category) => {
                            select.appendChild(new Option(category.name, String(category.id)));
                        });
                        select.value = currentValue;
                    });
                } else {
                    this._setOtpStatus("No eCommerce product categories found. Please add categories on the product eCommerce tab.", "warning");
                }
                this.el.querySelectorAll(".o_product_requisition_line").forEach((row) => {
                    this._refreshProductChoices(row);
                });
            })
            .catch(() => {
                this._setOtpStatus("Asset categories could not be loaded. Please refresh after upgrading the module.", "warning");
            });
    },

    _getRpcErrorMessage(error, fallback) {
        return error?.data?.message || error?.message || fallback;
    },

    _syncLineFilters(row, clearProduct = false) {
        if (!row) return;
        const category = row.querySelector(".o_req_product_category")?.value || "goods";
        const productInput = row.querySelector(".o_req_product_select");
        const productIdEl = row.querySelector(".o_req_product_id");
        const productDropdown = row.querySelector(".o_req_product_dropdown");
        const isService = category === "service";

        row.querySelectorAll(".o_req_goods_cell").forEach((cell) => {
            cell.style.display = isService ? "none" : "";
            cell.querySelectorAll("input, select, textarea").forEach((field) => {
                field.disabled = isService && !field.classList.contains("o_req_quantity");
            });
        });
        row.querySelectorAll(".o_req_service_cell").forEach((cell) => {
            cell.style.display = isService ? "" : "none";
            cell.querySelectorAll("input, select, textarea").forEach((field) => {
                field.disabled = !isService;
            });
        });

        if (clearProduct && productInput) {
            productInput.value = "";
            if (productIdEl) productIdEl.value = "";
            if (productDropdown) productDropdown.value = "";
            this._setSubtotal(row, 0);
        }
        this._refreshProductChoices(row);
        this._syncProductColumns();
    },

    _syncProductColumns() {
        const rows = Array.from(this.el.querySelectorAll(".o_product_requisition_line"));
        const hasService = rows.some((row) => row.querySelector(".o_req_product_category")?.value === "service");
        const hasGoods = rows.some((row) => (row.querySelector(".o_req_product_category")?.value || "goods") !== "service");

        this.el.querySelectorAll(".o_req_service_col").forEach((cell) => {
            cell.style.display = hasService ? "" : "none";
        });
        this.el.querySelectorAll(".o_req_goods_col").forEach((cell) => {
            cell.style.display = hasGoods ? "" : "none";
        });
    },

    _cacheProductOptions() {
        const list = this.el.querySelector("#o_req_product_options");
        this._allProductOptions = list ? Array.from(list.options).map((option) => ({
            value: option.value,
            productId: option.dataset.productId || "",
            productCategory: option.dataset.productCategory || "goods",
            assetCategoryIds: (option.dataset.assetCategoryIds || "").split(",").filter(Boolean),
            uom: option.dataset.uom || "",
            price: option.dataset.price || "0",
        })) : [];
    },

    _refreshProductChoices(row) {
        const input = row.querySelector(".o_req_product_select");
        const dropdown = row.querySelector(".o_req_product_dropdown");
        if (!input) return;

        const category = row.querySelector(".o_req_product_category")?.value || "goods";
        const assetCategory = row.querySelector(".o_req_asset_category")?.value || "";
        const currentValue = input.value;
        const currentProductId = row.querySelector(".o_req_product_id")?.value || "";
        const options = this._allProductOptions
            .filter((option) => option.productCategory === category)
            .filter((option) => !assetCategory || option.assetCategoryIds.includes(assetCategory));

        const list = this._ensureProductDatalist(row, input);
        list.innerHTML = "";
        if (dropdown) {
            dropdown.innerHTML = "";
            dropdown.appendChild(new Option("⌄", ""));
        }
        options.forEach((option) => {
            const datalistItem = document.createElement("option");
            datalistItem.value = option.value;
            datalistItem.dataset.productId = option.productId;
            datalistItem.dataset.productCategory = option.productCategory;
            datalistItem.dataset.assetCategoryIds = option.assetCategoryIds.join(",");
            datalistItem.dataset.uom = option.uom;
            datalistItem.dataset.price = option.price;
            list.appendChild(datalistItem);

            if (dropdown) {
                dropdown.appendChild(new Option(option.value, option.productId));
            }
        });
        if (!options.length) {
            list.appendChild(new Option("No products available", ""));
            if (dropdown) {
                const item = new Option("No products available", "");
                item.disabled = true;
                dropdown.appendChild(item);
            }
        }

        const selectedOption = options.find((option) => option.productId === currentProductId)
            || options.find((option) => option.value === currentValue);
        if (selectedOption) {
            input.value = selectedOption.value;
            if (dropdown) dropdown.value = selectedOption.productId;
            const productIdEl = row.querySelector(".o_req_product_id");
            if (productIdEl) productIdEl.value = selectedOption.productId;
        } else {
            if (dropdown) dropdown.value = "";
            const productIdEl = row.querySelector(".o_req_product_id");
            if (productIdEl) productIdEl.value = "";
            this._setSubtotal(row, 0);
        }
    },

    _ensureProductDatalist(row, input) {
        let list = row.querySelector(".o_req_product_options_filtered");
        if (!list) {
            list = document.createElement("datalist");
            list.className = "o_req_product_options_filtered";
            list.id = `o_req_product_options_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
            input.insertAdjacentElement("afterend", list);
        }
        input.setAttribute("list", list.id);
        return list;
    },

    _updateTotal() {
        let total = 0;
        this.el.querySelectorAll(".o_product_requisition_line").forEach((row) => {
            const input = row.querySelector(".o_req_product_select");
            const qtyEl  = row.querySelector(".o_req_quantity");
            if (!input || !qtyEl) return;
            const option = this._getProductOption(input);
            if (!option) return;
            const price  = parseFloat(option.price || "0");
            const qty    = parseFloat(qtyEl.value) || 0;
            total += price * qty;
        });
        const totalEl = this.el.querySelector(".o_req_grand_total");
        if (totalEl) totalEl.textContent = total > 0 ? this._fmt(total) : "—";
    },

    _fmt(value) {
        return value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    },

    _getProductOption(input) {
        if (!input || !input.value) return null;
        const row = input.closest(".o_product_requisition_line");
        return this._getFilteredProductOptions(row).find((option) => option.value === input.value) || null;
    },

    _getProductOptionById(productId, row) {
        if (!productId) return null;
        return this._getFilteredProductOptions(row).find((option) => option.productId === productId) || null;
    },

    _getFilteredProductOptions(row) {
        const category = row?.querySelector(".o_req_product_category")?.value || "goods";
        const assetCategory = row?.querySelector(".o_req_asset_category")?.value || "";
        return this._allProductOptions
            .filter((option) => option.productCategory === category)
            .filter((option) => !assetCategory || option.assetCategoryIds.includes(assetCategory));
    },
});
