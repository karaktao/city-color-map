<template>
  <div class="thumbs">
    <div class="thumb-list">
      <div v-for="img in thumbnails"
           :key="img.id"
           class="thumb-item"
           :class="{ active: img.id === selectedImageId }"
           @click="$emit('thumb-click', img)">
        <img :src="img.url" />
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  thumbnails: Array,
  selectedImageId: String
})
</script>

<style scoped>
.thumbs {
  border: 1px solid #444;
  height: 150px;
  overflow-x: auto;
}
.thumb-list {
  display: flex;
  padding: 10px;
}
.thumb-item {
  margin-right: 10px;
  cursor: pointer;
  border: 1px solid #888;
}
.thumb-item.active {
  border: 2px solid #00bfff;
}
.thumb-item img {
  width: 120px;
}
</style>
