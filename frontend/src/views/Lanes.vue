<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const refill = ref<any>(null)
const saving = ref<number | null>(null)
const error = ref('')

async function load() {
  rows.value = await api('/lanes')
}
onMounted(async () => {
  await load()
  try { refill.value = await api('/refills/run?location_id=1', { method: 'POST' }) } catch { /* */ }
})
async function toggleBlock(r: any) {
  saving.value = r.id
  error.value = ''
  try {
    await api(`/lanes/${r.id}/blocked`, { method: 'PATCH', body: JSON.stringify({ blocked: !r.blocked }) })
    await load()
    // 旗标与当前有效补货单同一事务更新，刷新小票保持同一口径
    refill.value = await api('/refills/latest?location_id=1')
  } catch {
    error.value = `保存失败：${r.slot_no} 封锁状态未变更，旗标与补货单已一并回滚`
    await load()
  } finally {
    saving.value = null
  }
}
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 右侧补货小票 · 封锁道补量恒为 0</p>
  <p v-if="error" class="vf-error">{{ error }}</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot" :class="{ 'vf-blocked': r.blocked }">
        <div class="vf-slot-no">
          {{ r.slot_no }}
          <span v-if="r.blocked" class="vf-blocked-badge">封锁</span>
        </div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': !r.blocked && r.gap > 0 }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">
          {{ r.stock }}/{{ r.capacity }} · {{ r.blocked ? '货道封锁' : '缺 ' + r.gap }}
        </div>
        <button class="vf-block-btn" :disabled="saving === r.id" @click="toggleBlock(r)">
          {{ saving === r.id ? '保存中…' : r.blocked ? '解除封锁' : '检修封锁' }}
        </button>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}<small v-if="l.blocked">（货道封锁）</small></span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 机面打印预览 —
      </p>
    </aside>
  </div>
</template>
