const { createApp, ref, computed, nextTick } = Vue;

createApp({
  setup() {
    const url = ref('');
    const loading = ref(false);
    const report = ref(null);

    // 进度状态
    const progress = ref(0);
    const stageIdx = ref(0);
    const elapsedSec = ref(0);
    let progressTimer = null;
    let elapsedTimer = null;

    // 5 个阶段：前 4 个用时间推进（后端实际是 4 个并发 GitHub 调用，整体约 3-5s），
    // 最后一个 AI 评分阶段慢慢爬到 95%，等响应到达后跳到 100%
    const stages = [
      { label: '解析仓库地址',          target: 8,  duration: 250 },
      { label: '抓取仓库元信息',        target: 28, duration: 1500 },
      { label: '统计语言分布与贡献者',  target: 48, duration: 1500 },
      { label: '汇总近期提交活动',      target: 62, duration: 1800 },
      { label: 'AI 智能评分中…',         target: 95, duration: 14000 },
    ];

    const currentStage = computed(() => stages[stageIdx.value] || stages[0]);
    const elapsedText = computed(() => {
      const s = elapsedSec.value;
      const mm = Math.floor(s / 60).toString().padStart(2, '0');
      const ss = (s % 60).toFixed(1).padStart(4, '0');
      return `${mm}:${ss}`;
    });

    // refs for canvas
    const langRef = ref(null);
    const commitRef = ref(null);
    const contribRef = ref(null);
    const radarRef = ref(null);

    let charts = [];
    const destroyCharts = () => { charts.forEach(c => c.destroy()); charts = []; };

    const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString());

    const scoreLevel = (s) => {
      if (s == null) return '';
      if (s >= 85) return 'level-a';
      if (s >= 70) return 'level-b';
      if (s >= 55) return 'level-c';
      return 'level-d';
    };

    const use = (v) => { url.value = v; analyze(); };

    const startProgress = () => {
      progress.value = 0;
      stageIdx.value = 0;
      elapsedSec.value = 0;

      const startTs = Date.now();
      elapsedTimer = setInterval(() => {
        elapsedSec.value = (Date.now() - startTs) / 1000;
      }, 100);

      const advance = (i) => {
        if (i >= stages.length) return;
        stageIdx.value = i;
        const start = i === 0 ? 0 : stages[i - 1].target;
        const target = stages[i].target;
        const duration = stages[i].duration;
        const tick = 50;
        const step = (target - start) / (duration / tick);
        progressTimer = setInterval(() => {
          if (progress.value + step >= target) {
            progress.value = target;
            clearInterval(progressTimer);
            progressTimer = null;
            if (i < stages.length - 1) {
              setTimeout(() => advance(i + 1), 60);
            }
          } else {
            progress.value += step;
          }
        }, tick);
      };
      advance(0);
    };

    const finishProgress = () => {
      if (progressTimer) { clearInterval(progressTimer); progressTimer = null; }
      if (elapsedTimer)  { clearInterval(elapsedTimer);  elapsedTimer  = null; }
      progress.value = 100;
      stageIdx.value = stages.length - 1;
    };

    const abortProgress = () => {
      if (progressTimer) { clearInterval(progressTimer); progressTimer = null; }
      if (elapsedTimer)  { clearInterval(elapsedTimer);  elapsedTimer  = null; }
    };

    const analyze = async () => {
      if (loading.value) return;
      if (!url.value.trim()) {
        ElementPlus.ElMessage.warning('请输入仓库 URL');
        return;
      }
      loading.value = true;
      destroyCharts();
      report.value = null;
      startProgress();

      try {
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: url.value.trim() }),
        });
        const data = await res.json();
        if (!res.ok) {
          abortProgress();
          ElementPlus.ElMessage.error(data.detail || '分析失败');
          loading.value = false;
          return;
        }
        finishProgress();
        // 短暂展示 100% 后再切换到结果视图
        setTimeout(async () => {
          report.value = data;
          loading.value = false;
          await nextTick();
          renderCharts(data);
        }, 350);
      } catch (e) {
        abortProgress();
        ElementPlus.ElMessage.error('请求失败：' + e.message);
        loading.value = false;
      }
    };

    const chartFont = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif";
    Chart.defaults.font.family = chartFont;
    Chart.defaults.color = '#475569';

    const PALETTE = ['#7c5cff', '#3ec8a3', '#f7b955', '#ff7a90', '#48b3ff', '#a886ff', '#34d399', '#fb923c'];

    const renderCharts = (d) => {
      // 语言饼图
      if (langRef.value && d.languages.length) {
        charts.push(new Chart(langRef.value, {
          type: 'doughnut',
          data: {
            labels: d.languages.map(l => l.name),
            datasets: [{
              data: d.languages.map(l => l.percent),
              backgroundColor: PALETTE,
              borderWidth: 2,
              borderColor: '#fff',
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
              legend: { position: 'right', labels: { boxWidth: 12, padding: 12 } },
              tooltip: { callbacks: { label: (c) => `${c.label}: ${c.parsed}%` } },
            },
          },
        }));
      }
      // 提交折线
      if (commitRef.value && d.commit_activity.length) {
        const ctx = commitRef.value.getContext('2d');
        const grad = ctx.createLinearGradient(0, 0, 0, 240);
        grad.addColorStop(0, 'rgba(124,92,255,0.35)');
        grad.addColorStop(1, 'rgba(124,92,255,0.02)');
        charts.push(new Chart(commitRef.value, {
          type: 'line',
          data: {
            labels: d.commit_activity.map(w => w.week_start),
            datasets: [{
              label: '每周提交数',
              data: d.commit_activity.map(w => w.commits),
              fill: true,
              tension: 0.35,
              borderColor: '#7c5cff',
              backgroundColor: grad,
              borderWidth: 2,
              pointRadius: 3,
              pointHoverRadius: 5,
              pointBackgroundColor: '#7c5cff',
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } },
              y: { grid: { color: '#f1f5f9' }, beginAtZero: true },
            },
          },
        }));
      }
      // 贡献者横条
      if (contribRef.value && d.top_contributors.length) {
        charts.push(new Chart(contribRef.value, {
          type: 'bar',
          data: {
            labels: d.top_contributors.map(c => c.login),
            datasets: [{
              label: '提交数',
              data: d.top_contributors.map(c => c.contributions),
              backgroundColor: '#3ec8a3',
              borderRadius: 6,
              barThickness: 18,
            }],
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              x: { grid: { color: '#f1f5f9' }, beginAtZero: true },
              y: { grid: { display: false } },
            },
          },
        }));
      }
      // AI 雷达
      if (d.ai && d.ai.available && radarRef.value) {
        const dims = d.ai.dimensions || {};
        charts.push(new Chart(radarRef.value, {
          type: 'radar',
          data: {
            labels: ['流行度', '活跃度', '社区', '可维护性', '文档'],
            datasets: [{
              label: '维度得分',
              data: [dims.popularity, dims.activity, dims.community, dims.maintainability, dims.documentation],
              borderColor: '#7c5cff',
              backgroundColor: 'rgba(124,92,255,0.18)',
              borderWidth: 2,
              pointBackgroundColor: '#7c5cff',
              pointRadius: 4,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              r: {
                suggestedMin: 0,
                suggestedMax: 100,
                ticks: { stepSize: 25, color: '#94a3b8', backdropColor: 'transparent' },
                grid: { color: '#e2e8f0' },
                angleLines: { color: '#e2e8f0' },
                pointLabels: { color: '#475569', font: { size: 13 } },
              },
            },
          },
        }));
      }
    };

    return {
      url, loading, report,
      progress, stageIdx, stages, currentStage, elapsedText,
      langRef, commitRef, contribRef, radarRef,
      fmt, scoreLevel, use, analyze,
    };
  },
}).use(ElementPlus).mount('#app');
