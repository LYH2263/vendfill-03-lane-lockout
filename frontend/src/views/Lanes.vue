<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const refill = ref<any>(null)
const saving = ref(false)
const error = ref('')

async function refresh() {
  rows.value = await api('/lanes')
}
onMounted(async () => {
  await refresh()
  try { refill.value = await api('/refills/run?location_id=1', { method: 'POST' }) } catch { /* */ }
})

async function toggleBlock(r: any) {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    // 旗标与当前有效补货单在同一提交里更新；失败则两者一起回滚
    const res = await api(`/lanes/${r.id}`, { method: 'PUT', body: JSON.stringify({ blocked: !r.blocked }) })
    await refresh()
    refill.value = res.order ?? await api('/refills/latest?location_id=1')
  } catch {
    error.value = `${r.slot_no} 封锁保存失败：货道旗标与补货单已一并回滚`
    await refresh()
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 右侧补货小票 · 格内按钮开/关检修封锁</p>
  <p v-if="error" class="vf-error">{{ error }}</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot" :class="{ 'vf-blocked': r.blocked }">
        <div class="vf-slot-no">{{ r.slot_no }}<span v-if="r.blocked" class="vf-lock-tag">封锁</span></div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.gap > 0 && !r.blocked }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 缺 {{ r.gap }}</div>
        <button class="vf-lock-btn" :class="{ on: r.blocked }" :disabled="saving" @click="toggleBlock(r)">
          {{ r.blocked ? '解除封锁' : '封锁' }}
        </button>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}<small v-if="l.status === 'blocked'">（货道封锁）</small></span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 机面打印预览 —
      </p>
    </aside>
  </div>
</template>
