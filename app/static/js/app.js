/* global Vue, echarts */
const { createApp } = Vue;

const PALETTE = ["#185FA5", "#378ADD", "#85B7EB", "#B5D4F4", "#D3D1C7"];
const ZONE_COLORS = { "1": "#185FA5", "2": "#378ADD", "3": "#85B7EB", "4": "#B5D4F4", none: "#B4B2A9" };
const STAGE_TEXT = {
  search: "正在检索 PubMed…",
  search_recent: "正在统计近N年文献…",
  trend: "正在统计年度趋势…",
  fetch: "正在抓取文献详情…",
  analyze: "正在匹配期刊指标并分析…",
  review: "AI 正在撰写中文综述…",
};

createApp({
  data() {
    return {
      keyword: "",
      years: 5,
      force: false,
      loading: false,
      stageText: "",
      progressPct: 0,
      errorMsg: "",
      result: null,
      examples: ["糖尿病视网膜病变", "CAR-T 细胞治疗", "长新冠", "阿尔茨海默病"],
      topN: 100,
      _charts: {},
      _es: null,
    };
  },
  computed: {
    reviewParas() {
      if (!this.result) return [];
      return this.result.review.markdown.split("\n").map((s) => s.trim()).filter(Boolean);
    },
    reviewSourceLabel() {
      if (!this.result) return "";
      const r = this.result.review;
      if (r.source === "llm") return (r.model || "LLM") + " 生成";
      return "统计模板生成（LLM 不可用）";
    },
    reviewWordCount() {
      if (!this.result) return "";
      return this.result.review.markdown.replace(/\s/g, "").length;
    },
    zoneItems() {
      if (!this.result) return [];
      const d = this.result.stats.zone_dist;
      const labels = { "1": "1 区", "2": "2 区", "3": "3 区", "4": "4 区", none: "暂无数据" };
      return Object.keys(labels).map((k) => ({
        label: labels[k],
        value: d[k] || 0,
        color: ZONE_COLORS[k],
      }));
    },
    printHtml() {
      return this.result ? this.buildPrintHtml(this.result) : "";
    },
  },
  watch: {
    result() {
      this.$nextTick(() => {
        this.renderCharts();
        this.scrollToResults();
      });
    },
  },
  methods: {
    fmt(n) {
      return n == null ? "—" : Number(n).toLocaleString("zh-CN");
    },
    pct(x) {
      return x == null ? "—" : Math.round(x * 100) + "%";
    },
    useExample(e) {
      this.keyword = e;
      this.start();
    },
    scrollToResults() {
      const el = document.querySelector(".result-meta");
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    start() {
      const kw = (this.keyword || "").trim();
      if (!kw) {
        this.errorMsg = "请先输入关键词";
        return;
      }
      if (this._es) this._es.close();
      this.errorMsg = "";
      this.result = null;
      this.loading = true;
      this.progressPct = 2;
      this.stageText = "正在发起检索…";

      const url = `/api/analyze/stream?q=${encodeURIComponent(kw)}&years=${this.years}&force=${this.force ? 1 : 0}`;
      const es = new EventSource(url);
      this._es = es;

      es.onmessage = (ev) => {
        let d;
        try {
          d = JSON.parse(ev.data);
        } catch (e) {
          return;
        }
        if (d.stage === "error") {
          this.loading = false;
          this.errorMsg = d.message || "检索失败，请稍后重试";
          es.close();
          return;
        }
        if (d.stage === "done") {
          this.result = d.result;
          this.loading = false;
          this.progressPct = 100;
          this.stageText = "完成";
          es.close();
          return;
        }
        if (d.stage === "search") this.progressPct = 8;
        else if (d.stage === "search_recent") this.progressPct = 16;
        else if (d.stage === "trend") this.progressPct = 26;
        else if (d.stage === "fetch") {
          const p = d.total ? d.done / d.total : 0;
          this.progressPct = 30 + 55 * p;
          this.stageText = `正在抓取文献详情（第 ${d.done}/${d.total} 批）…`;
          return;
        }
        else if (d.stage === "analyze") this.progressPct = 88;
        else if (d.stage === "review") this.progressPct = 94;
        this.stageText = STAGE_TEXT[d.stage] || this.stageText;
      };
      es.onerror = () => {
        this.loading = false;
        this.errorMsg = "连接中断（服务未启动或网络异常），请重试";
        es.close();
      };
    },

    renderCharts() {
      const r = this.result;
      if (!r) return;
      this.disposeCharts();

      // 词云
      const wc = echarts.init(this.$refs.wcChart);
      wc.setOption({
        series: [{
          type: "wordCloud",
          shape: "circle",
          sizeRange: [13, 36],
          rotationRange: [-30, 30],
          rotationStep: 15,
          gridSize: 6,
          drawOutOfBound: false,
          layoutAnimation: true,
          textStyle: {
            color: () => PALETTE[Math.floor(Math.random() * 3)] ,
            fontWeight: 500,
          },
          data: r.wordcloud.slice(0, 120),
          emphasis: { textStyle: { fontWeight: 700 } },
        }],
      });
      this._charts.wc = wc;

      // 年度趋势（逐年精确计数）
      const trend = r.stats.year_trend || r.stats.year_dist || {};
      const years = Object.keys(trend).sort();
      const tc = echarts.init(this.$refs.trendChart);
      tc.setOption({
        grid: { left: 44, right: 12, top: 16, bottom: 28 },
        tooltip: { trigger: "axis" },
        xAxis: { type: "category", data: years, axisLabel: { fontSize: 11 } },
        yAxis: { type: "value", axisLabel: { fontSize: 11 }, splitLine: { lineStyle: { color: "#EEF2F6" } } },
        series: [{
          type: "bar", data: years.map((y) => trend[y]), barWidth: "55%",
          itemStyle: { color: "#378ADD", borderRadius: [3, 3, 0, 0] },
        }],
      });
      this._charts.trend = tc;

      // 期刊 Top10
      const jt = r.stats.journal_top.slice().reverse();
      const jc = echarts.init(this.$refs.journalChart);
      jc.setOption({
        grid: { left: 8, right: 56, top: 8, bottom: 4, containLabel: true },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        xAxis: { type: "value", axisLabel: { fontSize: 11 }, splitLine: { lineStyle: { color: "#EEF2F6" } } },
        yAxis: {
          type: "category", data: jt.map((j) => j.journal), axisLabel: { fontSize: 11 },
        },
        series: [{
          type: "bar", data: jt.map((j) => j.count), barWidth: 12,
          itemStyle: { color: "#378ADD", borderRadius: [0, 3, 3, 0] },
          label: {
            show: true, position: "right", fontSize: 11, color: "#5F6B7A",
            formatter: (p) => {
              const j = jt[p.dataIndex];
              return j.if != null ? `${p.value} 篇 · IF ${j.if}` : `${p.value} 篇`;
            },
          },
        }],
      });
      this._charts.journal = jc;

      // 分区分布
      const zd = this.zoneItems.filter((z) => z.value > 0);
      const zc = echarts.init(this.$refs.zoneChart);
      zc.setOption({
        tooltip: { trigger: "item", formatter: "{b}：{c} 篇（{d}%）" },
        series: [{
          type: "pie", radius: ["52%", "74%"], center: ["50%", "50%"],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: "#fff", borderWidth: 2 },
          label: { show: false },
          data: zd.map((z) => ({ name: z.label, value: z.value, itemStyle: { color: z.color } })),
        }],
      });
      this._charts.zone = zc;
    },

    disposeCharts() {
      Object.values(this._charts).forEach((c) => c && c.dispose());
      this._charts = {};
    },

    async download(url, payload, fallbackName) {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) throw new Error("导出失败：" + resp.status);
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fallbackName;
      a.click();
      URL.revokeObjectURL(a.href);
    },
    exportMd() {
      this.download("/api/export/md", this.result, `文献洞察_${this.result.keyword}.md`)
        .catch((e) => alert(e.message));
    },
    exportDocx() {
      this.download("/api/export/docx", this.result, `文献洞察_${this.result.keyword}.docx`)
        .catch((e) => alert(e.message));
    },
    printReport() {
      window.print();
    },

    buildPrintHtml(r) {
      const s = r.stats;
      const esc = (t) => String(t == null ? "" : t)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      const paras = r.review.markdown.split("\n").map((x) => x.trim()).filter(Boolean)
        .map((x) => `<p>${esc(x)}</p>`).join("");
      const words = r.wordcloud.slice(0, 30).map((w) => `${esc(w.name)}（${w.value}）`).join("、");
      const rows = s.top_n.map((a) =>
        `<tr><td>${a.rank}</td><td>${esc(a.title)}</td><td>${esc(a.journal)}</td>` +
        `<td>${a.year}</td><td>${a.if}</td><td>${a.zone ? a.zone + "区" : "—"}</td></tr>`
      ).join("");
      return `
        <h1>文献洞察报告：${esc(r.keyword)}</h1>
        <p>生成时间：${esc(r.generated_at)}｜检索范围：近${r.params.years}年（${r.params.start_year}–${r.params.end_year}）</p>
        <p>命中总量：${s.total_count} 篇｜近${r.params.years}年：${s.recent_count} 篇｜纳入分析：${s.analyzed_count} 篇
        ｜中位 IF：${s.median_if == null ? "—" : s.median_if}｜1区占比：${this.pct(s.q1_ratio)}｜期刊指标匹配率：${this.pct(s.matched_ratio)}</p>
        <h2>一、领域综述</h2>${paras}
        <h2>二、研究热点词云（Top30）</h2><p>${words}</p>
        <h2>三、近${r.params.years}年影响力 Top${s.top_n.length} 文献</h2>
        <table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;width:100%">
          <thead><tr><th>#</th><th>标题</th><th>期刊</th><th>年份</th><th>IF</th><th>分区</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <p style="margin-top:14px;color:#888">数据来源：PubMed E-utilities｜期刊 IF / 分区为本地静态示例库（${esc(r.meta.journal_db_version)}）｜${r.review.source === "llm" ? "综述由 " + esc(r.review.model || "LLM") + " 生成，仅供参考" : "综述为统计模板自动生成，仅供参考"}</p>`;
    },
  },
  mounted() {
    window.addEventListener("resize", () => {
      Object.values(this._charts).forEach((c) => c && c.resize());
    });
  },
}).mount("#app");
