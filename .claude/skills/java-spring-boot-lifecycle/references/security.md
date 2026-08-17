# Spring Security

## Baseline SecurityFilterChain (Boot 3 style — component-based, no WebSecurityConfigurerAdapter)

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
class SecurityConfig {

  @Bean
  SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http
      .csrf(csrf -> csrf.disable())                      // stateless token APIs only — keep CSRF ON for session/cookie auth
      .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
      .authorizeHttpRequests(auth -> auth
        .requestMatchers("/actuator/health/**").permitAll()
        .requestMatchers("/api/v1/auth/**").permitAll()
        .anyRequest().authenticated())                   // deny-by-default: whitelist public, never blacklist private
      .oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()));
    return http.build();
  }
}
```

Principles:
- **Deny by default.** `anyRequest().authenticated()` (or `denyAll()`) last; explicitly permit the few public routes. Never enumerate protected routes.
- CSRF: disable only for stateless bearer-token APIs. If the browser sends a session cookie or you serve forms, CSRF stays on.
- Order matters in `authorizeHttpRequests` — first match wins.

## Choosing the auth model

| Situation | Do this |
|---|---|
| Service behind an identity provider (Keycloak, Auth0, Entra, Cognito) | **Resource server + JWT validation** — `spring-boot-starter-oauth2-resource-server`, set `spring.security.oauth2.resourceserver.jwt.issuer-uri`. Do not hand-roll token code. |
| Server-rendered app logging users in via IdP | `oauth2Login()` (OIDC) |
| Small self-contained app that owns its users | Username/password + your own JWT issuance is acceptable; steps below |
| Service-to-service | Client credentials flow, or mTLS at the mesh level |

Prefer the IdP route whenever one exists — password storage, rotation, MFA, and revocation are someone else's hardened problem.

## Self-issued JWT (only when justified)

- Sign with a real secret from env (≥ 256-bit for HS256) or better RS256/EdDSA keypair so other services can verify with the public key.
- Access tokens short-lived (≤ 15 min) + refresh tokens (rotated, revocable, stored hashed).
- Put only identity + roles in claims; never PII beyond what every consumer needs.
- Passwords: `PasswordEncoder` bean = `PasswordEncoderFactories.createDelegatingPasswordEncoder()` (bcrypt/argon2). Never a custom hash.
- Login endpoint: rate-limit and return the *same* error for unknown-user vs wrong-password (no user enumeration).

## Method security

`@EnableMethodSecurity`, then guard service methods that matter:

```java
@PreAuthorize("hasRole('ADMIN') or #ownerId == authentication.name")
public Order get(UUID id, String ownerId) { ... }
```

URL rules are the outer wall; method security protects against a controller mistake exposing a service. For row-level ownership checks (user A must not read user B's order), the check belongs in the service/query (`findByIdAndOwner(...)`) — this is the #1 real-world API vulnerability (BOLA/IDOR), and it is not solved by roles.

## CORS

Configure via `CorsConfigurationSource` bean with an explicit origin allowlist from config. Never `*` together with credentials. CORS must be handled by Spring Security's chain (`http.cors(withDefaults())`), not only `@CrossOrigin` sprinkles.

## Secrets & hardening checklist

- Secrets from env/secret manager; `application.yml` holds placeholders only (`${DB_PASSWORD}`). Add startup validation via `@ConfigurationProperties` so missing secrets kill boot.
- Actuator: expose only `health,info,metrics,prometheus`; everything else locked or on a separate management port (`management.server.port`).
- Set security headers where serving browsers (Boot defaults are decent; add CSP explicitly).
- Dependency CVE scanning in CI (see `build-ci-cd.md`); Spring Security patch releases are applied within days, not quarters.
- Log auth failures and privilege denials (WARN with principal + resource) — but never log tokens, passwords, or full Authorization headers.
- Validate file uploads (size, content type by magic bytes, storage outside webroot) and anything passed to queries — JPA parameter binding everywhere, string-concatenated JPQL/SQL never.

## Testing security

- `spring-security-test`: `@WithMockUser`, `SecurityMockMvcRequestPostProcessors.jwt()` for resource-server tests.
- Write the negative tests: anonymous → 401, wrong role → 403, other user's resource → 404/403. A security config without negative tests is unverified.
