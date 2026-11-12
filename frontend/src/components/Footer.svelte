<script lang="ts">
  const SOURCE = "https://github.com/nijaba/scrum-poker";
</script>

<footer>
  <span>Scrum poker is open source.</span>
  <a href={SOURCE} target="_blank" rel="noopener noreferrer">Source on GitHub</a>
</footer>

<style>
  footer {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
    gap: 0 6px;
    padding: 0 16px 8px;
    font-size: 13px;
    color: var(--text-3);
  }
  a {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: var(--link);
  }
</style>
