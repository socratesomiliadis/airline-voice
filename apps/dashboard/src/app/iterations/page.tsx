import { redirect } from "next/navigation";

export default function Page() {
  redirect("/evaluations?tab=history");
}
