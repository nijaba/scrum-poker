<script lang="ts">
  const SOURCE = "https://github.com/nijaba/scrum-poker";
  const HELP = `${SOURCE}/blob/main/docs/user-guide.md`;
  const WHY = `${SOURCE}/blob/main/docs/why-scrum-poker.md`;
</script>

<footer>
  <a href={HELP} target="_blank" rel="noopener noreferrer">Help</a>
  <span aria-hidden="true">·</span>
  <a href={WHY} target="_blank" rel="noopener noreferrer">Why scrum poker?</a>
  <span aria-hidden="true">·</span>
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
