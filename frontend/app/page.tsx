import { redirect } from "next/navigation";

// Root redirects to the gems library
export default function Home() {
  redirect("/gems");
}
