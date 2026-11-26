<template>
  <UContainer>
    <UPage>
      <template #left>
        <UPageAside>
          <DocsSidebar />
        </UPageAside>
      </template>

      <slot />
    </UPage>
  </UContainer>
</template>
