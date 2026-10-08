script_name = "TSDM 标点校正"
script_description = "根据TSDM字幕组标点规范，一键自动修正字幕中的中日文标点格式"
script_author = "小花 & Kimi"
script_version = "1"

local function replace_all(s, pat, repl)
    local n = 0
    local parts = {}
    local pos = 1
    while true do
        local i = s:find(pat, pos, true)
        if not i then
            parts[#parts + 1] = s:sub(pos)
            break
        end
        parts[#parts + 1] = s:sub(pos, i - 1)
        parts[#parts + 1] = repl
        n = n + 1
        pos = i + #pat
    end
    return table.concat(parts), n
end

local function collapse_spaces(s)
    while s:find("  ", 1, true) do
        s = replace_all(s, "  ", " ")
    end
    return s
end

local function trim(s)
    return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function fix_straight_quotes(text)
    local n = 0
    while true do
        local a = text:find('"', 1, true)
        if not a then break end
        local b = text:find('"', a + 1, true)
        if not b then break end
        text = text:sub(1, a - 1) .. "「" .. text:sub(a + 1, b - 1) .. "」" .. text:sub(b + 1)
        n = n + 1
    end
    return text, n
end

local function fix_ellipsis(text)
    local n = 0
    while true do
        local k
        text, k = replace_all(text, "……", "…"); n = n + k
        text, k = replace_all(text, "..", "…");  n = n + k
        if k == 0 then break end
    end
    return text, n
end

local function strip_punct_spaces(text)
    local puncts = { "?", "!", "「", "」", "…" }
    local n = 0
    local changed = true
    while changed do
        changed = false
        for _, p in ipairs(puncts) do
            local k
            text, k = replace_all(text, " " .. p, p); n = n + k
            if k > 0 then changed = true end
            text, k = replace_all(text, p .. " ", p); n = n + k
            if k > 0 then changed = true end
        end
    end
    return text, n
end

local function add_space_after(text)
    local n = 0
    local out = {}
    local i = 1
    local len = #text
    while i <= len do
        local b = text:byte(i)
        if (b == 0x3F or b == 0x21) and i < len then
            out[#out + 1] = string.char(b)
            local nb = text:byte(i + 1)
            local excluded = false
            if nb == 0x20 or nb == 0x5C then
                excluded = true
            elseif nb < 0x80 then
                excluded = (nb == 0x3F or nb == 0x21)
            elseif nb == 0xE3 then
                local b3 = text:byte(i + 3)
                excluded = (b3 == 0x8C or b3 == 0x8D)
            elseif nb == 0xE2 then
                excluded = (text:byte(i + 3) == 0xA6)
            end
            if not excluded then
                out[#out + 1] = " "
                n = n + 1
            end
            i = i + 1
        else
            local blen = 1
            if b >= 0xF0 then blen = 4
            elseif b >= 0xE0 then blen = 3
            elseif b >= 0xC0 then blen = 2 end
            out[#out + 1] = text:sub(i, i + blen - 1)
            i = i + blen
        end
    end
    return table.concat(out), n
end

local function new_stats()
    return { straight = 0, qleft = 0, qright = 0, q = 0, e = 0,
             ellipsis = 0, comma = 0, period = 0, ton = 0, fw = 0,
             strip = 0, addspace = 0 }
end

local function stats_total(st)
    return st.straight + st.qleft + st.qright + st.q + st.e +
           st.ellipsis + st.comma + st.period + st.ton + st.fw +
           st.strip + st.addspace
end

local function fix_text(text, opts, st)
    if opts.quotes then
        local n
        text, n = fix_straight_quotes(text);   st.straight = st.straight + n
        text, n = replace_all(text, "“", "「"); st.qleft = st.qleft + n
        text, n = replace_all(text, "”", "」"); st.qright = st.qright + n
    end
    if opts.qe then
        local n
        text, n = replace_all(text, "？", "?"); st.q = st.q + n
        text, n = replace_all(text, "！", "!"); st.e = st.e + n
    end
    if opts.ellipsis then
        local n
        text, n = fix_ellipsis(text); st.ellipsis = st.ellipsis + n
    end
    if opts.comma then
        local n
        text, n = replace_all(text, "，", " "); st.comma = st.comma + n
        text, n = replace_all(text, "。", " "); st.period = st.period + n
        text, n = replace_all(text, "、", " "); st.ton = st.ton + n
    end
    if opts.fwspace then
        local n
        text, n = replace_all(text, "　", " "); st.fw = st.fw + n
    end
    text = collapse_spaces(text)
    if opts.strip then
        local n
        text, n = strip_punct_spaces(text); st.strip = st.strip + n
    end
    if opts.addspace then
        local n
        text, n = add_space_after(text); st.addspace = st.addspace + n
    end
    return trim(text)
end

local function stats_lines(st)
    local lines = {}
    local items = {
        { st.comma,     "中文逗号（，）→ 半角空格" },
        { st.period,    "中文句号（。）→ 半角空格" },
        { st.ton,       "中文顿号（、）→ 半角空格" },
        { st.q,         "中文问号（？）→ 半角 ?" },
        { st.e,         "中文感叹号（！）→ 半角 !" },
        { st.qleft,     "中文左引号（“）→ 「" },
        { st.qright,    "中文右引号（”）→ 」" },
        { st.straight,  '成对直引号（"..."）→ 「...」' },
        { st.ellipsis,  "省略号（... / …… / ..）→ …" },
        { st.fw,        "全角空格（　）→ 半角空格" },
        { st.strip,     "保留标点前后多余空格去除" },
        { st.addspace,  "句中标点（?/!）后补空格" },
    }
    for _, it in ipairs(items) do
        if it[1] > 0 then
            lines[#lines + 1] = string.format("• %s: %d 处", it[2], it[1])
        end
    end
    if #lines == 0 then
        lines[1] = "（未发现需要修正的标点）"
    end
    return lines
end

local function show_options()
    local dlg = {
        { class = "label",    label = "处理范围", x = 0, y = 0 },
        { class = "dropdown", name = "scope", items = { "仅选中的行", "全部字幕行" },
          value = "仅选中的行", x = 1, y = 0, width = 2 },
        { class = "checkbox", name = "quotes",   label = "引号 → 「」（成对直引号 / 中文弯引号）",
          value = true,  x = 0, y = 1, width = 3 },
        { class = "checkbox", name = "qe",       label = "中文问号/感叹号 → 半角 ? !",
          value = true,  x = 0, y = 2, width = 3 },
        { class = "checkbox", name = "ellipsis", label = "省略号统一为 …",
          value = true,  x = 0, y = 3, width = 3 },
        { class = "checkbox", name = "comma",    label = "逗号 / 句号 / 顿号 → 半角空格",
          value = true,  x = 0, y = 4, width = 3 },
        { class = "checkbox", name = "fwspace",  label = "全角空格 → 半角空格",
          value = true,  x = 0, y = 5, width = 3 },
        { class = "checkbox", name = "strip",    label = "去除保留标点前后多余空格",
          value = true,  x = 0, y = 6, width = 3 },
        { class = "checkbox", name = "addspace", label = "句中标点（?/!）后补一格空格（省略号 / 句末除外）",
          value = true,  x = 0, y = 7, width = 3 },
    }
    local btn, res = aegisub.dialog.display(dlg, { "确定", "取消" })
    if btn == "确定" then return res end
    return nil
end

local function show_report(lines, total, scope_desc, nlines)
    local dlg = {
        { class = "label", label = string.format("处理完成：%s，共处理 %d 行", scope_desc, nlines),
          x = 0, y = 0 },
    }
    local y = 1
    for _, l in ipairs(lines) do
        dlg[#dlg + 1] = { class = "label", label = "  " .. l, x = 0, y = y }
        y = y + 1
    end
    if total > 0 then
        dlg[#dlg + 1] = { class = "label", label = string.format("总计修正：%d 处", total), x = 0, y = y }
    else
        dlg[#dlg + 1] = { class = "label", label = "所选内容无需修正。", x = 0, y = y }
    end
    aegisub.dialog.display(dlg, { "好——！" })
end

local function main(subs, sel)
    local opts = show_options()
    if not opts then aegisub.cancel() end

    local st = new_stats()
    local indices
    if opts.scope == "全部字幕行" then
        indices = {}
        for i = 1, #subs do indices[#indices + 1] = i end
    else
        indices = sel
    end

    local changed, processed = 0, 0
    for _, i in ipairs(indices) do
        local line = subs[i]
        if line.class == "dialogue" then
            processed = processed + 1
            local newtext = fix_text(line.text, opts, st)
            if newtext ~= line.text then
                line.text = newtext
                subs[i] = line
                changed = changed + 1
            end
        end
    end

    aegisub.log("【标点校正】处理 %d 行，修改 %d 行\n%s\n总计修正：%d 处\n",
        processed, changed, table.concat(stats_lines(st), "\n"), stats_total(st))

    show_report(stats_lines(st), stats_total(st), opts.scope, processed)
    return subs, sel
end

aegisub.register_macro(script_name, script_description, main)