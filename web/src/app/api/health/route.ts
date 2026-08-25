import { getHealth } from "@/lib/queries";

export const dynamic = "force-dynamic";

/** GET /api/health — liveness plus what data is currently loaded. */
export async function GET(): Promise<Response> {
  try {
    const health = await getHealth();
    return Response.json(health, { status: health.status === "ok" ? 200 : 503 });
  } catch (error) {
    return Response.json(
      {
        status: "error",
        message: error instanceof Error ? error.message : "unknown database error",
      },
      { status: 503 },
    );
  }
}
